"""Quick debug test for config page fill behavior."""
import pytest
from tests.e2e.pages.config_page import ConfigPage


@pytest.fixture
def config_page(authenticated_page):
    return ConfigPage(authenticated_page)


def test_debug_config_fill(config_page, test_token, live_server):
    """Debug config fill behavior."""
    import time

    # Navigate and wait for load
    config_page.navigate(live_server)
    config_page.wait_for_page_loaded()

    # Check initial api_id value
    initial_value = config_page.get_api_id_value()
    print(f"Initial api_id value: {repr(initial_value)}")

    # Check configManager state
    has_changes_before = config_page.page.evaluate("() => window.configManager?.hasChanges")
    config_api_id = config_page.page.evaluate("() => window.configManager?.config?.api_id")
    original_api_id = config_page.page.evaluate("() => window.configManager?.originalConfig?.api_id")
    print(f"Before fill: hasChanges={has_changes_before}, config.api_id={repr(config_api_id)}, original.api_id={repr(original_api_id)}")

    # Fill empty
    config_page.set_api_id_value("")
    time.sleep(1)

    # Check after fill
    after_value = config_page.get_api_id_value()
    has_changes_after = config_page.page.evaluate("() => window.configManager?.hasChanges")
    config_api_id_after = config_page.page.evaluate("() => window.configManager?.config?.api_id")
    print(f"After fill(''): input={repr(after_value)}, hasChanges={has_changes_after}, config.api_id={repr(config_api_id_after)}")

    assert False, "Debug output"
