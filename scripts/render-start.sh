#!/usr/bin/env bash

# Export the virtual environment path (it's inside backend/)
export PATH="$PWD/backend/.venv/bin:$PATH"

# Limit thread usage to reduce memory footprint on Render
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false

WORKER_PID=""
UVICORN_PID=""
# RQ's first SIGTERM is a "warm shutdown": if a job is mid-flight it just
# waits for that job to finish (up to RQ_GRAPH_TIMEOUT=7200s) before exiting.
# Left unbounded, the old instance stays alive for hours alongside the new
# one Render just started, blowing the account's concurrency limit on every
# redeploy that lands mid-job. Only a SECOND SIGTERM makes RQ cold-shutdown
# immediately (rq.Worker.request_force_stop), so bound the wait and escalate.
WORKER_SHUTDOWN_GRACE_SECONDS="${WORKER_SHUTDOWN_GRACE_SECONDS:-25}"

# Bash does not forward signals to background jobs on its own, so without this
# trap a redeploy's SIGTERM only reaches uvicorn (the foreground process) and
# the backgrounded worker lingers until Render hard-kills the container. That
# left a stale "seekr-ingestion-worker" registration for the next deploy to
# collide with. Forward the signal to both children and wait for them to exit.
cleanup() {
  echo "Shutdown signal received, forwarding to child processes..."
  [ -n "$UVICORN_PID" ] && kill -TERM "$UVICORN_PID" 2>/dev/null
  if [ -n "$WORKER_PID" ]; then
    kill -TERM "$WORKER_PID" 2>/dev/null
    for _ in $(seq 1 "$WORKER_SHUTDOWN_GRACE_SECONDS"); do
      kill -0 "$WORKER_PID" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$WORKER_PID" 2>/dev/null; then
      echo "Worker still mid-job after ${WORKER_SHUTDOWN_GRACE_SECONDS}s, forcing cold shutdown..."
      kill -TERM "$WORKER_PID" 2>/dev/null
      sleep 2
      kill -KILL "$WORKER_PID" 2>/dev/null
    fi
  fi
  wait
  exit 0
}
trap cleanup TERM INT

# Enable the background worker only when explicitly requested to avoid Render memory spikes.
if [ "${RENDER_ENABLE_INGESTION_WORKER:-true}" = "true" ]; then
  echo "Scheduling RQ Ingestion Worker to start in ${RENDER_WORKER_START_DELAY_SECONDS:-0} seconds..."
  # exec replaces the subshell with the python process (same PID) once the
  # delay elapses, so kill -TERM "$WORKER_PID" above reaches it directly.
  (sleep "${RENDER_WORKER_START_DELAY_SECONDS:-0}" && echo "Starting RQ Ingestion Worker now..." && exec python -m backend.ingestion_worker.main) &
  WORKER_PID=$!
else
  echo "Skipping RQ Ingestion Worker startup on Render to conserve memory."
fi

echo "Starting FastAPI Web Server..."
# Run the web server in the background too so the trap can forward signals to
# it, then wait for whichever child exits first (or a shutdown signal).
uvicorn backend.fabric_api.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers --forwarded-allow-ips="*" --limit-concurrency "${RENDER_MAX_CONCURRENCY:-4}" &
UVICORN_PID=$!

wait -n "$UVICORN_PID" ${WORKER_PID:+"$WORKER_PID"}
cleanup
