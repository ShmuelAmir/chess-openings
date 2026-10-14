import asyncio

import httpx
import pytest

from chess_com import ChessComAccountNotFoundError, ChessComClient


def archives_when_answered(status, username="magnus"):
    """The archive listing of an account Chess.com answers with `status`."""
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"archives": []}))

    async def run():
        async with ChessComClient(transport=transport) as client:
            return await client.get_archives(username)

    return asyncio.run(run())


@pytest.mark.parametrize("status", [404, 410])
def test_an_unknown_account_is_the_account_not_found_error(status):
    with pytest.raises(ChessComAccountNotFoundError) as error:
        archives_when_answered(status, username="nobody")

    assert str(error.value) == "No Chess.com account named 'nobody'"


@pytest.mark.parametrize("status", [429, 500])
def test_another_failure_is_not_the_account_not_found_error(status):
    with pytest.raises(httpx.HTTPStatusError):
        archives_when_answered(status)


def test_a_known_account_lists_its_archives():
    assert archives_when_answered(200) == []
