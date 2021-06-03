import logging

from aiohttp import web
from faker import Faker

logger = logging.getLogger(__name__)


async def create_sso_with_auth(is_logged_in: bool, sso_user_id: str):
    fake = Faker(["en-GB"])
    email = fake.email()
    auth_to_me = {
        "Bearer token-1": {
            "email": email,
            "contact_email": email,
            "related_emails": [],
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "user_id": sso_user_id,
        }
    }
    return await create_sso(
        is_logged_in, iter(["some-code"]), iter(["token-1"]), auth_to_me
    )


async def create_sso(is_logged_in, codes, tokens, auth_to_me):
    number_of_times = 0
    latest_code = None

    async def handle_authorize(request):
        logger.debug("handle_authorize")
        nonlocal number_of_times
        nonlocal latest_code

        number_of_times += 1

        if not is_logged_in:
            return web.Response(status=200, text="This is the login page")

        state = request.query["state"]
        latest_code = next(codes)
        return web.Response(
            status=302,
            headers={
                "Location": request.query["redirect_uri"]
                + f"?state={state}&code={latest_code}"
            },
        )

    async def handle_token(request):
        if (await request.post())["code"] != latest_code:
            return web.json_response({}, status=403)

        token = next(tokens)
        return web.json_response({"access_token": token}, status=200)

    async def handle_me(request):
        if request.headers["authorization"] in auth_to_me:
            return web.json_response(
                auth_to_me[request.headers["authorization"]], status=200
            )

        return web.json_response({}, status=403)

    sso_app = web.Application()
    sso_app.add_routes(
        [
            web.get("/o/authorize/", handle_authorize),
            web.post("/o/token/", handle_token),
            web.get("/api/v1/user/me/", handle_me),
        ]
    )
    sso_runner = web.AppRunner(sso_app)
    await sso_runner.setup()
    sso_site = web.TCPSite(sso_runner, "0.0.0.0", 8005)
    await sso_site.start()

    def get_number_of_times():
        return number_of_times

    logger.debug("create_sso")
    return sso_runner.cleanup, get_number_of_times
