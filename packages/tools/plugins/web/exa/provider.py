"""Stub for plugins.web.exa.provider."""
class ExaClient:
    async def search(self, query: str, **kw) -> list: return []
def _get_exa_client(**kw): return ExaClient()
def get_provider(): return ExaClient()
