import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Create scheduler BEFORE event loop is running
scheduler = AsyncIOScheduler()
print(f"Scheduler created. State: {scheduler.state}")

fired = []

async def my_task():
    fired.append(datetime.now())
    print(f"  Fired at {datetime.now()}")

async def main():
    print(f"Starting scheduler in event loop")
    scheduler.start()
    print(f"Scheduler state after start: {scheduler.state}")

    trigger = IntervalTrigger(seconds=2, start_date=datetime.now() + timedelta(seconds=1))
    scheduler.add_job(my_task, trigger)

    print(f"Waiting 10s")
    await asyncio.sleep(10)
    print(f"Fired {len(fired)} times")
    scheduler.shutdown()

asyncio.run(main())