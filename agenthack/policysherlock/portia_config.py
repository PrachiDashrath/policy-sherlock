from portia import Config, DefaultToolRegistry
from portia.open_source_tools.browser_tool import BrowserTool, BrowserInfrastructureOption

def get_portia_config():
    return Config(
        tool_registry=DefaultToolRegistry(
            tools=[
                BrowserTool(infrastructure=BrowserInfrastructureOption.PLAYWRIGHT)
            ]
        )
    )
