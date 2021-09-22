import asyncio

import asyncpg
from dotenv import dotenv_values

async def run():
    pool = await asyncpg.create_pool(dsn=dotenv_values()["DSN"],)
    if not pool:
        raise RuntimeError("pool is none")
    con = await pool.acquire()
    try:
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS other (
                key varchar(255),
                value varchar(255)
            );
            """
        )
        # key = input("key:")
        # value = input("value:")
        # await con.execute(
        #     f"""
        #     INSERT INTO other (key, value)
        #     VALUES ($1, $2); 
        #     """, 
        #     key,
        #     value,
        # )
        
        getkey = input("getkey:")
        result = await con.fetch(
            """
            SELECT * FROM other WHERE key=$1;
            """, getkey
        )
        print(result)
        for key in result:
            for k, v in key.items():
                print(k,v)
                print()
                #print(key.get("value"))
        
    except Exception as e:
        print(e)
    
asyncio.run(run())
