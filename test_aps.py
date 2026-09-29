import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

fired = []

async def my_task():
    fired.append(datetime.now())

async def main():
    scheduler = AsyncIOScheduler()
    scheduler.start()
    start = datetime.now() + timedelta(seconds=5)
    print(f'Start time: {start}')
    trigger = IntervalTrigger(seconds=10, start_date=start)
    scheduler.add_job(my_task, trigger)
    print(f'Initial next_run_time: {scheduler.get_jobs()[0].next_run_time}')
    await asyncio.sleep(30)
    print(f'Total fires: {len(fired)}')
    for f in fired:
        print(f'  fired at {f}, offset from start: {(f - start).total_seconds()}s')
    scheduler.shutdown()

asyncio.run(main())