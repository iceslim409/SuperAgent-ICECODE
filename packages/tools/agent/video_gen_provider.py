"""Stub for agent.video_gen_provider."""
class VideoGenProvider:
    name = "stub"
    async def generate(self, prompt: str, **kw): return {"url": "", "error": "not configured"}

def get_default_provider(): return VideoGenProvider()
def list_providers() -> list: return []

COMMON_ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]
DEFAULT_ASPECT_RATIO = "16:9"
COMMON_RESOLUTIONS = ["1920x1080", "1280x720", "854x480", "3840x2160"]
DEFAULT_RESOLUTION = "1280x720"
VideoGenConfig = dict

def error_response(msg: str) -> dict: return {"error": msg, "url": ""}
class VideoGenRequest: pass
class VideoGenResult: pass
