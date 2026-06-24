#!/usr/bin/env python3
"""MTGO freeze diagnostic sampler — no root, no strace needed.

Attaches by name to MTGO.exe and samples /proc every second. When it detects a
stall (one core pinned for >=2s) OR you create /tmp/mtgo-freeze.mark, it runs a
high-resolution "deep capture": per-thread CPU%, run-state, kernel wchan, and
current syscall — which tells us whether the freeze is CPU-bound (WPF/GC/layout),
lock-bound (futex), network-bound (recvfrom/poll) or disk-bound (D-state/read).

Usage:
    python3 mtgo-diag.py                 # run; reproduce the freeze in MTGO
    touch /tmp/mtgo-freeze.mark          # force a capture at the moment it freezes
Logs -> ./diag/sample.csv  and  ./diag/capture-*.log
"""
import os, time, glob, sys, subprocess, pathlib

HZ = os.sysconf("SC_CLK_TCK")
OUT = pathlib.Path(__file__).resolve().parent / "diag"
OUT.mkdir(exist_ok=True)
SAMPLE = OUT / "sample.csv"
MARK = "/tmp/mtgo-freeze.mark"

SYS = {0:"read",1:"write",7:"poll",16:"ioctl",23:"select",24:"sched_yield",
       35:"nanosleep",45:"recvfrom",47:"recvmsg",202:"futex",228:"clock_nanosleep",
       230:"clock_nanosleep",232:"epoll_wait",270:"pselect6",271:"ppoll",
       281:"epoll_pwait",-1:"(running-userspace)"}

def find_pid():
    for d in glob.glob("/proc/[0-9]*"):
        try:
            if pathlib.Path(d, "comm").read_text().strip() == "MTGO.exe":
                return int(os.path.basename(d))
        except Exception:
            pass
    return None

def thread_cpu(pid):
    """return {tid: ticks} of utime+stime per thread"""
    out = {}
    for t in glob.glob(f"/proc/{pid}/task/*/stat"):
        try:
            f = pathlib.Path(t).read_text()
            tid = int(f.split()[0])
            fields = f[f.rindex(")")+2:].split()
            out[tid] = int(fields[11]) + int(fields[12])  # utime+stime (0-indexed after state)
        except Exception:
            pass
    return out

def thread_info(pid, tid):
    base = f"/proc/{pid}/task/{tid}"
    try:
        st = pathlib.Path(base, "stat").read_text()
        state = st[st.rindex(")")+2]
    except Exception:
        state = "?"
    try:
        wchan = pathlib.Path(base, "wchan").read_text().strip() or "0"
    except Exception:
        wchan = "?"
    try:
        sc = pathlib.Path(base, "syscall").read_text().strip()
        nr = int(sc.split()[0]) if sc.split() and sc.split()[0].lstrip("-").isdigit() else -1
        scname = SYS.get(nr, f"sys{nr}")
    except Exception:
        scname = "?"
    return state, wchan, scname

def meminfo():
    d = {}
    for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":")[0], line.split()[1]
        d[k] = int(v)
    return d

def rss_mb(pid):
    try:
        for line in pathlib.Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS"):
                return int(line.split()[1]) // 1024
    except Exception:
        return -1

def deep_capture(pid, reason):
    ts = time.strftime("%H%M%S")
    cap = OUT / f"capture-{ts}.log"
    print(f"  >>> FREEZE CAPTURE ({reason}) -> {cap.name}")
    with cap.open("w") as f:
        f.write(f"# deep capture {time.strftime('%H:%M:%S')} reason={reason} pid={pid}\n")
        try:
            ss = subprocess.run(["ss","-tnp"], capture_output=True, text=True, timeout=4).stdout
            f.write("== ss -tnp (MTGO sockets) ==\n")
            f.write("\n".join(l for l in ss.splitlines() if f"pid={pid}" in l) + "\n\n")
        except Exception as e:
            f.write(f"ss failed: {e}\n")
        for i in range(20):  # ~6s at 0.3s
            a = thread_cpu(pid); time.sleep(0.3); b = thread_cpu(pid)
            deltas = sorted(((b[t]-a.get(t,b[t]), t) for t in b), reverse=True)[:8]
            f.write(f"-- snap {i} {time.strftime('%H:%M:%S')} --\n")
            for dticks, tid in deltas:
                cpu = dticks / HZ / 0.3 * 100
                state, wchan, sc = thread_info(pid, tid)
                f.write(f"   tid={tid:<8} cpu={cpu:5.0f}%  state={state}  syscall={sc:<22} wchan={wchan}\n")
            f.flush()
    return cap

def main():
    print("waiting for MTGO.exe ...")
    pid = None
    while pid is None:
        pid = find_pid(); time.sleep(1)
    print(f"attached to MTGO.exe pid={pid}. Reproduce the freeze now. Ctrl-C to stop.")
    SAMPLE.write_text("ts,cpu_pct,threads,running,disk_D,top_tid,top_cpu,top_state,top_syscall,top_wchan,rss_mb,mem_avail_mb,swap_used_mb\n")
    hot = 0
    while True:
        if find_pid() != pid:
            print("MTGO exited."); return
        a = thread_cpu(pid); time.sleep(1.0); b = thread_cpu(pid)
        deltas = sorted(((b[t]-a.get(t,b[t]), t) for t in b), reverse=True)
        total = sum(max(0,d) for d,_ in deltas) / HZ / 1.0 * 100
        nR = nD = 0; states = {}
        for _, tid in deltas:
            s,_,_ = thread_info(pid, tid); states[tid]=s
            if s == "R": nR += 1
            elif s == "D": nD += 1
        top_d, top_tid = deltas[0]
        top_cpu = top_d / HZ / 1.0 * 100
        ts, tw, tsc = thread_info(pid, top_tid)
        mi = meminfo()
        row = [time.strftime("%H:%M:%S"), f"{total:.0f}", len(b), nR, nD, top_tid,
               f"{top_cpu:.0f}", ts, tsc, tw, rss_mb(pid),
               mi["MemAvailable"]//1024, (mi["SwapTotal"]-mi["SwapFree"])//1024]
        line = ",".join(str(x) for x in row)
        with SAMPLE.open("a") as f: f.write(line+"\n")
        print(f"{row[0]} cpu={total:4.0f}% R={nR} D={nD} top:tid{top_tid} {top_cpu:3.0f}% {ts} {tsc} {tw}")
        # freeze triggers
        if total >= 85: hot += 1
        else: hot = 0
        if hot >= 2:
            deep_capture(pid, f"cpu-pinned {total:.0f}%"); hot = 0
        if os.path.exists(MARK):
            os.remove(MARK); deep_capture(pid, "manual-mark")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\nstopped.")
