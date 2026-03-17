from sdl2_solid_dose.opentrons import OTFlexProtocol


if __name__ == "__main__":
    protocol = OTFlexProtocol(simulation=True)
    try:
        plan = [
            {
                "action": "transfer",
                "pip_name": "p1000",
                "compound": "acid_stock",
                "source_labware": "al_plate_24",
                "source_well": "A1",
                "dest_labware": "plate_96_1",
                "dest_well": "A1",
                "volume": 200,
            },
            {
                "action": "transfer",
                "pip_name": "p1000",
                "compound": "base_stock",
                "source_labware": "al_plate_24",
                "source_well": "A2",
                "dest_labware": "plate_96_1",
                "dest_well": "A2",
                "volume": 200,
            },
            {
                "action": "mix",
                "pip_name": "p1000",
                "compound": "acid_stock",
                "labware": "plate_96_1",
                "well": "A1",
                "volume": 100,
                "cycles": 2,
            },
            {
                "action": "mix",
                "pip_name": "p1000",
                "compound": "base_stock",
                "labware": "plate_96_1",
                "well": "A2",
                "volume": 100,
                "cycles": 2,
            },
        ]
        protocol.execute_plan(plan)
        protocol.ot.home()
    finally:
        protocol.close()
