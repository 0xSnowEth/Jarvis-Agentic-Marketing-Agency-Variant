import os
import sys
import time
import logging
import argparse
import subprocess
import schedule
from datetime import datetime

from schedule_store import is_schedulable_job, load_schedule, schedule_signature
from schedule_utils import parse_iso_date

# Configure logging specifically for the daemon layer
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler_daemon.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("SchedulerDaemon")


def run_pipeline(client: str, topic: str, images: list = None, videos: list = None, job_id: str | None = None, draft_name: str | None = None):
    """
    Spawns pipeline.py in an isolated subprocess.
    If the LLM crashes or Meta Tokens expire, this process terminates gracefully
    and returns an exit code without crashing the continuously running Scheduler Daemon.
    """
    logger.info(f"? [TRIGGERED] Spawning pipeline.py for '{client}'...")
    try:
        cmd = [sys.executable, "pipeline.py", "--client", client, "--topic", topic]
        if job_id:
            cmd.extend(["--job-id", job_id])
        if draft_name:
            cmd.extend(["--draft-name", draft_name])
        if images:
            for img in images:
                cmd.extend(["--image", img])
        if videos:
            for video in videos:
                cmd.extend(["--video", video])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            logger.info(f"? [SUCCESS] Pipeline completed successfully for '{client}'.")
            logger.info(f"--- PIPELINE OUTPUT ---\n{result.stdout.strip()}\n-----------------------")
        else:
            logger.error(f"? [FAILURE] Pipeline crashed for '{client}' (Exit Code {result.returncode}).")
            logger.error(f"Pipeline StdErr: {result.stderr}")
            logger.error(f"Pipeline StdOut: {result.stdout}")

    except Exception as e:
        logger.error(f"? [FATAL] Failed to spawn subprocess for '{client}': {str(e)}")


def run_date_bound_pipeline(client: str, topic: str, scheduled_date: str, images: list = None, videos: list = None, job_id: str | None = None, draft_name: str | None = None):
    target_date = parse_iso_date(scheduled_date)
    today = datetime.now().date()
    if target_date is None:
        logger.warning(f"Skipping one-off job {job_id or 'unknown'} because scheduled_date '{scheduled_date}' is invalid.")
        return schedule.CancelJob
    if today < target_date:
        return None
    if today > target_date:
        logger.warning(f"Skipping expired one-off job {job_id or 'unknown'} for '{client}' because {scheduled_date} has already passed.")
        return schedule.CancelJob

    run_pipeline(client=client, topic=topic, images=images, videos=videos, job_id=job_id, draft_name=draft_name)
    return schedule.CancelJob


def load_schedule_config(filepath: str = "schedule.json") -> list:
    if not os.path.exists(filepath):
        logger.error(f"Config file '{filepath}' not found.")
        return []
    return load_schedule(filepath)


def convert_to_24hr(time_str: str) -> str:
    try:
        t = datetime.strptime(time_str.strip(), "%I:%M %p")
        return t.strftime("%H:%M")
    except ValueError:
        return time_str


def build_schedule(jobs: list):
    seen_signatures = set()

    for index, job in enumerate(jobs):
        if not is_schedulable_job(job):
            logger.info(
                f"Skipping non-executable job {job.get('job_id', index)} with status '{job.get('status', 'approved')}'."
            )
            continue

        signature = schedule_signature(job)
        if signature in seen_signatures:
            logger.warning(
                f"Skipping duplicate active job {job.get('job_id', index)} for client '{job.get('client')}' at {job.get('time')}."
            )
            continue
        seen_signatures.add(signature)

        client = job.get("client")
        topic = job.get("topic")
        days = job.get("days", [])
        raw_time = job.get("time")
        job_id = job.get("job_id")
        scheduled_date = str(job.get("scheduled_date") or "").strip()

        if not all([client, topic, raw_time, job_id]):
            logger.warning(f"Skipping malformed job index {index}: {job}")
            continue
        if not days and not scheduled_date:
            logger.warning(f"Skipping job {job_id} because it has neither days nor scheduled_date.")
            continue

        post_time = convert_to_24hr(raw_time)
        images = job.get("images", [])
        videos = job.get("videos", [])
        draft_name = str(job.get("draft_name") or "").strip() or None

        if scheduled_date:
            target_date = parse_iso_date(scheduled_date)
            if target_date and target_date < datetime.now().date():
                logger.warning(f"Skipping past one-off job {job_id} scheduled for {scheduled_date} at {raw_time}.")
                continue
            schedule.every().day.at(post_time).do(
                run_date_bound_pipeline,
                client=client,
                topic=topic,
                scheduled_date=scheduled_date,
                images=images,
                videos=videos,
                job_id=job_id,
                draft_name=draft_name,
            )
            continue

        if any(str(day).strip().lower() == "everyday" for day in days):
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for day in days:
            day_lower = str(day).strip().lower()
            if day_lower == "monday":
                schedule.every().monday.at(post_time).do(run_pipeline, client=client, topic=topic, images=images, videos=videos, job_id=job_id, draft_name=draft_name)
            elif day_lower == "tuesday":
                schedule.every().tuesday.at(post_time).do(run_pipeline, client=client, topic=topic, images=images, videos=videos, job_id=job_id, draft_name=draft_name)
            elif day_lower == "wednesday":
                schedule.every().wednesday.at(post_time).do(run_pipeline, client=client, topic=topic, images=images, videos=videos, job_id=job_id, draft_name=draft_name)
            elif day_lower == "thursday":
                schedule.every().thursday.at(post_time).do(run_pipeline, client=client, topic=topic, images=images, videos=videos, job_id=job_id, draft_name=draft_name)
            elif day_lower == "friday":
                schedule.every().friday.at(post_time).do(run_pipeline, client=client, topic=topic, images=images, videos=videos, job_id=job_id, draft_name=draft_name)
            elif day_lower == "saturday":
                schedule.every().saturday.at(post_time).do(run_pipeline, client=client, topic=topic, images=images, videos=videos, job_id=job_id, draft_name=draft_name)
            elif day_lower == "sunday":
                schedule.every().sunday.at(post_time).do(run_pipeline, client=client, topic=topic, images=images, videos=videos, job_id=job_id, draft_name=draft_name)
            else:
                logger.warning(f"Unrecognized day '{day}' for client '{client}'. Skipping this day rule.")


def main():
    parser = argparse.ArgumentParser(description="Agent Scheduler Daemon")
    parser.add_argument("--dry-run", action="store_true", help="Load and print the schedule to verify, then exit immediately without starting the daemon.")
    args = parser.parse_args()

    jobs = load_schedule_config()
    if not jobs:
        logger.info("No jobs found in schedule.json. Starting in idle mode ? waiting for hot-reload...")
    else:
        build_schedule(jobs)

    if args.dry_run:
        print("\n" + "=" * 50)
        print("?? SCHEDULER DRY-RUN VERIFICATION")
        print("=" * 50)
        configured_jobs = schedule.get_jobs()
        if not configured_jobs:
            print("No jobs were scheduled. Check your schedule.json parsing.")
        else:
            print(f"Total Triggers Queued: {len(configured_jobs)}\n")
            for i, j in enumerate(configured_jobs, 1):
                print(f"[{i}] Job Scheduled:")
                print(f"    Trigger: {j}")
                print(f"    Next Run: {j.next_run}")
                print("-" * 50)
        print("\nDry-run complete. Exiting.\n")
        sys.exit(0)

    logger.info(f"Started Scheduler Daemon. Currently actively tracking {len(schedule.get_jobs())} triggers.")
    logger.info("Background heartbeats running. Awaiting scheduled times...")

    config_path = "schedule.json"
    last_mod_time = os.path.getmtime(config_path) if os.path.exists(config_path) else 0

    try:
        while True:
            current_mod_time = os.path.getmtime(config_path) if os.path.exists(config_path) else 0
            if current_mod_time > last_mod_time:
                logger.info("schedule.json modified on disk! Hot-reloading triggers...")
                schedule.clear()
                new_jobs = load_schedule_config(config_path)
                build_schedule(new_jobs)
                last_mod_time = current_mod_time
                logger.info(f"Hot-reload complete. Now tracking {len(schedule.get_jobs())} triggers.")

            with open(".daemon_heartbeat", "w", encoding="utf-8") as f:
                f.write(str(time.time()))

            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Scheduler Daemon manually stopped via Keyboard Interrupt.")


if __name__ == "__main__":
    main()
