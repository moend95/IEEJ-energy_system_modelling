from core.io_types import GuiInput, SimOutput


def run_simulation(inp: GuiInput) -> SimOutput:

    out = SimOutput()

    if inp.highways:
        out.TEST_NUMBER = inp.tractor_turn_radius * 2

    return out