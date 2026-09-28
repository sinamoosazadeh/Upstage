import asyncio
from apex.telegram.signaling import MessageTokenBucket
async def main():
    t=[0.0]
    bucket=MessageTokenBucket(clock=lambda:t[0])
    n=0
    for _ in range(20):
        await bucket.acquire(); n+=1
    t[0]=0.95
    while bucket.available()>=1:
        await bucket.acquire(); n+=1
    print('sent_between_t0_and_t0.95=',n,'seconds=',t[0])
asyncio.run(main())
