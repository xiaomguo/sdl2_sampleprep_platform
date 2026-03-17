from ..ur5_rtde_gripper import Location
from typing import Union, List

import inspect
import pprint
import json
import uuid
from datetime import datetime
from collections import OrderedDict


class BaseContainer:
    def __init__(self,
                 well_name: str,
                 tray_name: str,
                 needle_depth: dict,
                 location: Location):
        # IDs
        self._unique_id = None
        self.user_defined_id = None
        self.well_name = well_name
        self.tray_name = tray_name
        self.tray = None
        self._used = False  # assume all containers are not used at the beginning
        # location
        self.location = location
         # Container properties
        self.needle = needle_depth
        self.empty_weight_mg = None
        self.weight_history = OrderedDict()
        self.measured_weight = OrderedDict()
        self.units = {'liquid': 'ml', 'solid': 'mg'}
        self.summary = None
        self.process_parameters = {'temperature': None,
                                   'time': None,
                                   'stirring': None}

    @property
    def unique_id(self):
        return self._unique_id

    def _assign_uuid(self):
        if self._unique_id is not None:
            print(f'Unique ID already set as {self.unique_id}')
        else:
            self._unique_id = str(uuid.uuid4())

    @property
    def used(self):
        return self._used

    @used.setter
    def used(self, value: bool):
        if not isinstance(value, bool):
            raise ValueError("Used must be a boolean value.")
        self._used = value
        self._assign_uuid()

    def add_weight_measurement(self, sample_name: str, weight: float):
        if not self.used:
            self.used = True

        if weight < 0:
            raise ValueError("Weight cannot be negative.")
        
        self.weight_history[sample_name] = weight

        if sample_name.lower() == 'empty':
            self.empty_weight_mg = weight
            self._last_weight_mg = weight  # initialize tracking
        else:
            # Calculate addition relative to previous step
            added_weight = weight - self._last_weight_mg
            self.measured_weight[sample_name] = added_weight
            self._last_weight_mg = weight  # update last weight

        self._update_plate_json()

    
    def _update_plate_json(self):
        """Update the tray JSON file with the current container information."""
        if self.tray:
            self.tray.save_to_json()
        else:
            pass

    def get_info(self):
        """Retrieve container information."""
        self.summary = {key: value for key, value in {
            "well_name": self.well_name,
            "tray_name": self.tray_name,
            "unique_id": self._unique_id,
            "user_defined_id": self.user_defined_id,
            "weight_history": dict(self.weight_history), # display as regular dict
            "measured_weight": dict(self.measured_weight),
            "empty_weight_mg": self.empty_weight_mg,
        }.items() if value is not None}
        return self.summary

    def __repr__(self):
        return self.get_info()


class Container(BaseContainer):
    def __init__(self,
                 well_name: str,
                 tray_name: str,
                 needle_depth: dict,
                 location: Location,
                 mlh_location: Location,
                 gripper: dict,
                 volume_ml: list):
        super().__init__(
            well_name=well_name,
            tray_name=tray_name,
            needle_depth=needle_depth,
            location=location
        )

        self.mlh_location = mlh_location
        self.gripper = gripper
        self.contents = OrderedDict()
        self.total_volume = 0.0

        self.min_volume_ml = volume_ml[0]
        self.max_volume_ml = volume_ml[1]

    def add_content(self, key: str, value: float):
        """Add liquid contents to the container."""
        if not self.used:
            self.used = True

        if value <= 0:
            raise ValueError("Content volume must be greater than zero.")
        if self.total_volume + value > self.max_volume_ml:
            raise ValueError("Adding this content exceeds the container's maximum volume.")

        if key in self.contents:
            self.contents[key] += value
        else:
            self.contents[key] = value
        self.total_volume = sum(self.contents.values())

        self._update_plate_json()

    def add_min_volume(self, value: float):
        """Set the minimum volume of the container."""
        if value < 0:
            raise ValueError("Minimum volume cannot be negative.")
        self.min_volume_ml = value

    def get_info(self):
        """Retrieve container information."""
        self.summary = {key: value for key, value in {
            "well_name": self.well_name,
            "tray_name": self.tray_name,
            "unique_id": self._unique_id,
            "user_defined_id": self.user_defined_id,
            "weight_history": self.weight_history,
            "total_volume": self.total_volume,
            "contents": self.contents,
            "units": self.units,
            "empty_weight_mg": self.empty_weight_mg,
        }.items() if value is not None}
        return self.summary


class vial_stock(Container):
    def __init__(self,
                 well_name: str,
                 tray_name: str,
                 needle_depth: dict,
                 location: Location,
                 mlh_location: Location,
                 gripper: dict,
                 volume_ml: list):
        super().__init__(
            mlh_location=mlh_location,
            gripper=gripper,
            volume_ml=volume_ml,
            well_name=well_name,
            tray_name=tray_name,
            needle_depth=needle_depth,
            location=location
        )
        self.cap = True  # Assuming cap is always true for HPLC
        self.layer = None
        self.lc_data_dir = []
        self.lc_peaks = []
        self.sampled_from = {}
        self.lc_instrument_parameters = {'injection_volume': [],
                                         'method': [],
                                         'instrument_location': []}

    def toggle_cap(self, state: bool):
        """Set the cap status to the specified state (True for on, False for off)."""
        if not isinstance(state, bool):
            raise ValueError("State must be a boolean value.")
        self.cap = state

    def add_layer_aliquot(self, layer: str, volume: Union[float, int]):
        """Add an aliquot of a layer from the extraction vial
        
        :param layer: The layer to add to the vial, this should top or bottom. This could also be aqueous or organic.
        :param volume: The volume of the layer added to the vial expressed in microliters.
        """
        self.layer = layer
        self.add_content(layer, volume)


    def update_lc_instrument_parameters(self, injection_volume: float, method: str, instrument_location: str):
        """ Update the LC instrument parameters

        :param injection_volume: the volume injected into the LC
        :param method: the method used for the LC analysis
        :param instrument_location: the location of the LC instrument
        """
        self.lc_instrument_parameters['injection_volume'].append(injection_volume)
        self.lc_instrument_parameters['method'].append(method)
        self.lc_instrument_parameters['instrument_location'].append(instrument_location)
        self._update_plate_json()

    def add_lc_data_directory(self, path: str):
        """ Associates the directory containing the data files for future reference

        :param path: the full path where the output of the lc data was stored
        """
        self.lc_data_dir.append(path)
        self._update_plate_json()

    def add_lc_peaks(self, peaks: List[float]):
        """ Associates the LC peaks to the container for future reference

        :param peaks: a list of LC peaks
        """
        self.lc_peaks.append(peaks)
        self._update_plate_json()


class vial_sample(BaseContainer):
    def __init__(self,
                 well_name: str,
                 tray_name: str,
                 needle_depth: dict,
                 location: Location,
                 volume_ml: list):
        super().__init__(
            well_name=well_name,
            tray_name=tray_name,
            needle_depth=needle_depth,
            location=location
        )

        self.min_volume_ml = volume_ml[0]
        self.max_volume_ml = volume_ml[1]
        self.total_volume = 0.0
        self.solvent_name = None

    def volume_tracking(self, volume_ml: float):
        """Track the volume of the solvent."""
        if volume_ml < 0:
            raise ValueError("Volume cannot be negative.")
        available_volume = self.max_volume_ml - self.total_volume
        if volume_ml > available_volume:
            raise ValueError("Volume exceeds available capacity.")

        self.total_volume = + volume_ml

    def add_solvent_info(self, solvent_name, user_id):
        """Add solvent information."""
        self.solvent_name = solvent_name
        self.user_defined_id = user_id


class dose_stock(Container):
    def __init__(self,
                 well_name: str,
                 tray_name: str,
                 needle_depth: dict,
                 location: Location,
                 mlh_location: Location,
                 gripper: dict,
                 volume_ml: list):
        super().__init__(
            mlh_location=mlh_location,
            gripper=gripper,
            volume_ml=volume_ml,
            well_name=well_name,
            tray_name=tray_name,
            needle_depth=needle_depth,
            location=location
        )

        self.lc_vials = {}
        self.video_files = {}

    def add_lc_vial(self, layer: str, well_name: str):
        self.lc_vials[layer] = well_name

    def add_video_files(self, recording: str, file_name: str):
        self.video_files[recording] = file_name
        
class dose_stock_back(Container):
    def __init__(self,
                 well_name: str,
                 tray_name: str,
                 needle_depth: dict,
                 location: Location,
                 mlh_location: Location,
                 gripper: dict,
                 volume_ml: list):
        super().__init__(
            mlh_location=mlh_location,
            gripper=gripper,
            volume_ml=volume_ml,
            well_name=well_name,
            tray_name=tray_name,
            needle_depth=needle_depth,
            location=location
        )

        self.lc_vials = {}
        self.video_files = {}

    def add_lc_vial(self, layer: str, well_name: str):
        self.lc_vials[layer] = well_name

    def add_video_files(self, recording: str, file_name: str):
        self.video_files[recording] = file_name

class Holder:
    def __init__(self,
                 well_name: str,
                 location: Location,
                 mlh_location: Location = None,
                ):
        self.well_name = well_name
        self.location = location
        self.mlh_location = mlh_location
        self.container = None
        self.used = False  # assume all containers are not used at the beginning

    def add_container(self, container: BaseContainer):
        """Add a container to the holder."""
        if not isinstance(container, BaseContainer):
            raise ValueError("The provided object is not a valid BaseContainer instance.")
        if self.container or self.used:
            raise ValueError("Holder can only contain one container.")
        else:
            self.container = container
            self.used = True

    def remove_container(self):
        """Remove the container from the holder."""
        if self.container:
            self.container = None
            self.used = False
        else:
            raise ValueError("No container to remove.")    


class Tray:
    def __init__(self,
                 tray_name: str,
                 wells: List[Union[BaseContainer, Holder]],
                 log_filename: str = datetime.now().strftime('%Y%m%d_%H%M%S'),
                 path: str = './'):
        self.tray_name = tray_name
        self.wells = {container.well_name: container for container in wells}
        self.well_names = list(self.wells.keys())
        self.save_directory = path
        self.filename = log_filename
        self.json_file = f"{ self.save_directory}{self.filename}_{tray_name}.json"
        self._add_plate()
        # Save the initial state to a JSON file

    @classmethod
    def from_container_class(cls,
                             container_class: type,
                             tray_name: str,
                             locations: dict,
                             mlh_locations: dict = None,
                             gripper: dict = None,
                             needle_depth: dict = None,
                             volume_ml: list = None,
                             **kwargs):
        """Create a tray from a dictionary of well_name to locations."""

        wells = {}
        init_params = inspect.signature(container_class.__init__).parameters

        if mlh_locations:
            if set(locations.keys()) != set(mlh_locations.keys()):
                raise ValueError("Locations and mlh_locations must have the same keys.")
        else:
            mlh_locations = {key: None for key in locations.keys()}

        for well, location in locations.items():
            mlh_location = mlh_locations.get(well)

            # Base arguments
            container_args = {
                "well_name": well,
                "tray_name": tray_name,
                "location": location,
                "needle_depth": needle_depth,
            }

            # Include anything else passed via **kwargs if relevant
            for key, val in kwargs.items():
                if key in init_params:
                    container_args[key] = val

            if 'mlh_location' in init_params:
                container_args['mlh_location'] = mlh_location
            if 'gripper' in init_params:
                container_args['gripper'] = gripper
            if 'volume_ml' in init_params:
                container_args['volume_ml'] = volume_ml

            if container_class == Holder:
                container_args = {
                    "well_name": well,
                    "location": location,
                    "mlh_location": mlh_location
                }

            wells[well] = container_class(**container_args)

        return cls(tray_name=tray_name, wells=list(wells.values()), **kwargs)

    def update_file_directory(self, path: str):
        self.save_directory = path
# add 
    def update_filename(self, filename: str):
        self.filename = filename

    def _add_plate(self):
        """Add the plate to the tray."""
        for container in self.wells.values():
            container.tray = self

    def _get_index_from_name(self, name: str) -> Union[int, str]:
        """Get the index of a container by its user_defined_id"""
        for w in self.wells.values():
            if name == w.user_defined_id:
                return w
        else:
            raise ValueError(f"{name} container not found in tray.")

    def get_next_available(self) -> Union[BaseContainer, None]:
        """Return the next available container that is not used."""
        for container in self.wells.values():
            if not container.used:
                return container
        return None

    def mark_used(self, container: BaseContainer, used: bool):
        """Update the used status of a container."""
        if container.well_name in self.wells:
            self.wells[container.well_name].used = used
        else:
            raise ValueError("The specified container is not part of this tray.")

    def add_content(self, container: BaseContainer, key: str, value: float):
        """Add content to a specific container."""
        if container.well_name in self.wells:
            self.wells[container.well_name].add_content(key, value)
        else:
            raise ValueError("The specified container is not part of this tray.")

    def add_weight_measurement(self, container: BaseContainer, sample_name: str, weight: float):
        """Update the weight history of a specific container."""
        if container.well_name in self.wells:
            self.wells[container.well_name].add_weight_measurement(sample_name, weight)
        else:
            raise ValueError("The specified container is not part of this tray.")

    def solvent_info_from_file(self, filename: str = "solvents.json"):
        """Load solvent information from a JSON file and associate it with the correct wells."""
        if self.tray_name != "solvent":
            raise ValueError("This method is only applicable to solvent trays.")
        
        path = "./solvent_library/"  # Fixed path to the folder where this module is saved

        with open(f"{path}{filename}", "r") as f:
            data = json.load(f)['solvents']
        
        for k,v in data.items():
            if k in self.wells:
                self.wells[k].add_solvent_info(v.get("name"),v.get("user_defined_id"))
            
    def get_summary(self, print_summary: bool = False, save: bool = False, filename: str = None):
        """Display tray information and optionally save it to a JSON file."""

        tray_info = {
            "tray_name": self.tray_name,
            "containers": {well: container.get_info() for well, container in self.wells.items()}
        }

        if print_summary:
            pprint.pprint(tray_info)

        if save:
            if filename is None:
                date = datetime.now().strftime('%Y%m%d_%H%M%S')
                file = f"{date}_{self.tray_name}_summary"
            else:
                file = filename
            with open(f"{file}.json", "w") as f:
                json.dump(tray_info, f, indent=4)

        return tray_info

    def save_to_json(self):
        """Save plate summary to a JSON file."""
        with open(self.json_file, "w") as f:
            json.dump(self.get_summary(), f, indent=4)

    def __getitem__(self, key: Union[str, int]) -> BaseContainer:
        """Retrieve a container by well_name, unique_id, or index."""
        if isinstance(key, int):
            return list(self.wells.values())[key]
        elif isinstance(key, str):
            # Search by well_name
            if key in self.wells:
                return self.wells[key]
            # Search by unique_id
            for container in self.wells.values():
                if container.unique_id == key:
                    return container
        raise KeyError(f"No container found for key: {key}")

    def __repr__(self):
        return f"Plate({self.tray_name})"
    
