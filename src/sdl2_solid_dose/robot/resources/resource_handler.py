from .containers import Tray, vial_stock, dose_stock, vial_sample, dose_stock_back
from ..ur5_rtde_gripper import Location
from typing import Tuple

# Simple local implementation to replace hein_robots dependencies
Cartesian = Tuple[float, float]  # Type alias for (x, y) coordinates

import string

#can input values for gripper close and open here
class Handler:
    """
    A class to handle the creation of trays, their containers, and their locations.
    
    This class is used to create a grid of locations for a given tray type and to 
    initialize the tray with the appropriate information for each container type (i.e., vial size).  
    """

    # TODO: update these values with your platform's values
    CONTAINER_INFO = {
        'vial_stock': {
            'gripper': {'h': 0.92},
            'needle': {'aspirate': 51, 'dispense': 15},
            'volumes': [0, 2],
            'container_class': vial_stock
        },
        'dose_stock': {
            'gripper': {'h': 0.89},
            'needle': {'aspirate': 37, 'dispense': 25},
            'volumes': [0, 1],
            'container_class': dose_stock
        },
        'dose_stock_back': {
            'gripper': {'h': 0.89},
            'needle': {'aspirate': 37, 'dispense': 25},
            'volumes': [0, 1],
            'container_class': dose_stock_back
        },
        'vial_sample': {
            'gripper': {'h': 0.92},
            'needle': {'aspirate': 75, 'dispense': 15},
            'volumes': [2, 16],
            'container_class': vial_sample
        },
    }

    def __init__(self):
        return

    @staticmethod    
    def _translate(location, x=0, y=0, z=0):
        """
        Translate a location by a given x, y, and z offset.
        :param location: the location to translate
        :param x: the x offset
        :param y: the y offset
        :param z: the z offset
        :return: the translated location using the hien_robots Location class
        """    
        if isinstance(location, dict):
            location = location['l']
        else:
            pass

        # Create Location with position=[x,y,z] and orientation=[rx,ry,rz] format
        new_position = [location[0] + x, location[1] + y, location[2] + z]
        new_orientation = [location[3], location[4], location[5]]
        new_location = Location(position=new_position, orientation=new_orientation)
        
        return new_location
    # convert list with coordinate into location - can add option to keep using the list (will give more flexibility)

    def create_grid(self, A1_vial_location, rows : int , columns: int,
                  spacing: tuple):
        """
        Create a grid dictionary given the top-left well coordinates, the number of rows and columns,
        and the well spacing (x,y). 

        :param location: the location of the top-left well
        :param rows: the number of rows on the plate
        :param columns: the number of columns on the plate
        :param spacing: the spacing
        """

        grid_columns = string.ascii_uppercase[:columns]
        grid_rows = range(1,rows+1)
        
        grid_dict = {}

        for i, r in enumerate(grid_columns):
            x_diff = -spacing[0] * i  # B1 is in negative X direction from A1
            for c in grid_rows:
                y_diff = -spacing[1] * (c-1)  # A2 is in negative Y direction from A1
                key = f"{r}{c}"
                grid_dict[key] = self._translate(A1_vial_location, x=x_diff, y=y_diff)
                
        return grid_dict

    def initialize_tray(self, tray_name, locations, file_directory: str = None):
        container_type = self.CONTAINER_INFO[tray_name]
        tray_args = {
            'container_class': container_type.get('container_class'),
            'locations': locations,
            'tray_name': tray_name,
            'path': file_directory
        }
        if 'gripper' in container_type:
            tray_args['gripper'] = container_type['gripper']
        if 'needle' in container_type:
            tray_args['needle_depth'] = container_type['needle']
        if 'volumes' in container_type:
            tray_args['volume_ml'] = container_type['volumes']
        tray = Tray.from_container_class(**tray_args)
        return tray

    def make_tray(self, top_left, rows: int = 0, columns: int = 0, spacing: Cartesian = (0, 0),
                  tray_name: str = "hplc", file_directory: str = None,
                  solvent_file : str = None):
        """Create an instance of Plate class to help with vial handling"""
#only function we will need to call - to create a plate or tray
        grid = self.create_grid(top_left, rows, columns, spacing)

        tray = self.initialize_tray(tray_name, grid, file_directory=file_directory)

        if tray_name == 'solvent' and solvent_file:
            tray.solvent_info_from_file(solvent_file)
        else:
            pass

        return tray
#file directory can do later / same with solvent directory
#top_left is A1 location
#use move to location function (linear & absolute) rather than move.l (our move l is a relative movement of the robot)
#top left coordinates of well, optional coordinate of top most well (in case tray has mlh), tray name (one of three things HPLC, solvent, extraction)
