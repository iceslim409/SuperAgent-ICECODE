"""Stub for plugins.web.parallel.provider."""
class ParallelClient:
    async def search(self, query: str, **kw) -> list: return []
def _get_parallel_client(**kw): return ParallelClient()
def _get_async_parallel_client(**kw): return ParallelClient()
def get_provider(): return ParallelClient()
