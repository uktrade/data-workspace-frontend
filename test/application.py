

# Run the application proper in a way that is as possible to production
# The environment must be the same as in the Dockerfile
async def create_application(env=lambda: {}):
    proc = await asyncio.create_subprocess_exec(
        "/dataworkspace/start-test.sh",
        env={**os.environ, **env()},
        preexec_fn=os.setsid,
    )

    celery_proc = await asyncio.create_subprocess_exec(
        "/dataworkspace/start-celery.sh",
        env={**os.environ, **env()},
        preexec_fn=os.setsid
    )

    async def _cleanup_application():
        try:
            os.killpg(os.getpgid(celery_proc.pid), signal.SIGTERM)
            await asyncio.sleep(3)

            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            await asyncio.sleep(1)

            if os.path.exists("/home/django/celerybeat.pid"):
                # pylint: disable=unspecified-encoding
                with open("/home/django/celerybeat.pid") as f:
                    print(f.read())
                try:
                    os.unlink("/home/django/celerybeat.pid")
                except FileNotFoundError:
                    pass
        except ProcessLookupError:
            pass

    return _cleanup_application
