import asyncio


async def background_task(name, delay):
    try:
        print(f"Background Task {name} started")
        await asyncio.sleep(delay)
        print(f"Background Task {name} finished")
        return f"Result from {name}"
    except asyncio.CancelledError:
        print(f"Background Task {name} was cancelled")
        raise


async def main():
    # 启动后台任务
    task1 = asyncio.create_task(background_task("Task1", 5))
    task2 = asyncio.create_task(background_task("Task2", 1))

    # 主流程可以继续执行其他任务
    print("Main process is doing other work")
    # await asyncio.sleep(2)  # 其他工作
    print("Main process finished other work")

    # 主流程在这里不等待后台任务完成，并立即输出
    print("All background tasks started and main process is done")

    # 可选：如果你需要在程序结束前等待所有后台任务完成
    # 这一步可以根据需要调整。
    # await asyncio.gather(task1, task2)


if __name__ == "__main__":
    asyncio.run(main())