from sdl2_solid_dose.ph_module.image_req_client import pHAnalyzer


LIGHT_LIST = [
    (0, 0, 0),
    (5, 5, 5),
    (10, 10, 10),
    (15, 15, 15),
    (20, 20, 20),
]


def run_light_sweep(light_list=None):
    light_list = light_list or LIGHT_LIST
    results = []

    with pHAnalyzer() as analyzer:
        for r, g, b in light_list:
            print(f"\n--- Testing with LED RGB = ({r}, {g}, {b}) ---")
            photo_result = analyzer.request_photo(light_setting=(r, g, b))
            if photo_result and isinstance(photo_result, tuple):
                image_path, original_filename = photo_result
                analysis = analyzer.analyze_image(image_path, original_filename)
                results.append(
                    {
                        "led": (r, g, b),
                        "filename": original_filename,
                        "analysis": analysis,
                    }
                )
            else:
                print("Photo capture failed.")

    print("\nSummary of results:")
    for res in results:
        print(f"LED {res['led']}: Filename: {res['filename']}, Analysis: {res['analysis']}")

    return results


if __name__ == "__main__":
    run_light_sweep()
