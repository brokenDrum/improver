#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# (C) British Crown Copyright 2017-2019 Met Office.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""Script to extrapolate input data given advection velocity fields."""

import iris
import numpy as np
from iris import Constraint
from iris.cube import CubeList

from improver.argparser import ArgParser
from improver.nowcasting.forecasting import CreateExtrapolationForecast
from improver.utilities.cli_utilities import load_json_or_none
from improver.utilities.load import load_cube
from improver.utilities.save import save_netcdf
from improver.wind_calculations.wind_components import ResolveWindComponents


def main(argv=None):
    """Extrapolate data forward in time."""

    parser = ArgParser(
        description="Extrapolate input data to required lead times.")
    parser.add_argument("input_filepath", metavar="INPUT_FILEPATH",
                        type=str, help="Path to input NetCDF file.")
    parser.add_argument("output_filepath", metavar="OUTPUT_FILEPATH",
                        help="The output path for the resulting NetCDF")

    speed = parser.add_argument_group('Advect using files containing speed and'
                                      ' direction')
    speed.add_argument("--advection_speed_filepath", type=str, help="Path"
                       " to input file containing advection speeds,"
                       " usually wind speeds, on multiple pressure levels.")
    speed.add_argument("--advection_direction_filepath", type=str,
                       help="Path to input file containing the directions from"
                       " which advection speeds are coming (180 degrees from"
                       " the direction in which the speed is directed). The"
                       " directions should be on the same grid as the input"
                       " speeds, including the same vertical levels.")
    speed.add_argument("--pressure_level", type=int, default=75000, help="The"
                       " pressure level in Pa to extract from the multi-level"
                       " advection_speed and advection_direction files. The"
                       " velocities at this level are used for advection.")
    parser.add_argument("--orographic_enhancement_filepaths", nargs="+",
                        type=str, default=None, help="List or wildcarded "
                        "file specification to the input orographic "
                        "enhancement files. Orographic enhancement files are "
                        "compulsory for precipitation fields.")
    parser.add_argument("--json_file", metavar="JSON_FILE", default=None,
                        help="Filename for the json file containing "
                        "required changes to the attributes. "
                        "Defaults to None.", type=str)
    parser.add_argument("--max_lead_time", type=int, default=360,
                        help="Maximum lead time required (mins).")
    parser.add_argument("--lead_time_interval", type=int, default=15,
                        help="Interval between required lead times (mins).")
    parser.add_argument("--u_and_v_filepath", type=str, help="Path to u and v"
                        " cubelist.")

    accumulation_args = parser.add_argument_group(
        'Calculate accumulations from advected fields')
    accumulation_args.add_argument(
        "--accumulation_fidelity", type=int, default=0,
        help="If set, this CLI will additionally return accumulations"
        " calculated from the advected fields. This fidelity specifies the"
        " time interval in minutes between advected fields that is used to"
        " calculate these accumulations. This interval must be a factor of"
        " the lead_time_interval.")

    args = parser.parse_args(args=argv)

    v_cube = load_cube(args.u_and_v_filepath,
                       "precipitation_advection_y_velocity", allow_none=True)
    u_cube = load_cube(args.u_and_v_filepath,
                       "precipitation_advection_x_velocity", allow_none=True)

    # Load Cubes and JSON
    speed_cube = direction_cube = None

    input_cube = load_cube(args.input_filepath)
    orographic_enhancement_cube = load_cube(
        args.orographic_enhancement_filepaths, allow_none=True)

    spath, dpath = (args.advection_speed_filepath,
                    args.advection_direction_filepath)
    level_constraint = Constraint(pressure=args.pressure_level)
    if spath and dpath:
        try:
            speed_cube = load_cube(spath, constraints=level_constraint)
            direction_cube = load_cube(dpath, constraints=level_constraint)
        except ValueError as err:
            raise ValueError(
                '{} Unable to extract specified pressure level from given '
                'speed and direction files.'.format(err))

    attributes_dict = load_json_or_none(args.json_file)
    # Process Cubes
    result = process(
        input_cube, u_cube, v_cube, speed_cube, direction_cube,
        orographic_enhancement_cube, attributes_dict, args.max_lead_time,
        args.lead_time_interval, args.accumulation_fidelity)

    # Save Cube
    save_netcdf(result, args.output_filepath)


def process(input_cube, u_cube, v_cube, speed_cube, direction_cube,
            orographic_enhancement_cube=None, attributes_dict=None,
            max_lead_time=360, lead_time_interval=15, accumulation_fidelity=0):
    """Module  to extrapolate input cubes given advection velocity fields.

    Args:
        input_cube (iris.cube.Cube):
            The input Cube to be processed.
        u_cube (iris.cube.Cube):
            Cube with the velocities in the x direction.
            Must be used with v_cube.
            s_cube and d_cube must be None.
        v_cube (iris.cube.Cube):
            Cube with the velocities in the y direction.
            Must be used with u_cube.
            s_cube and d_cube must be None.
        speed_cube (iris.cube.Cube):
            Cube containing advection speeds, usually wind speed.
            Must be used with d_cube.
            u_cube and v_cube must be None.
        direction_cube (iris.cube.Cube):
            Cube from which advection speeds are coming. The directions
            should be on the same grid as the input speeds, including the same
            vertical levels.
            Must be used with d_cube.
            u_cube and v_cube must be None.
        orographic_enhancement_cube (iris.cube.Cube):
            Cube containing the orographic enhancement fields. May have data
            for multiple times in the cube.
            Default is None.
        attributes_dict (dict):
            Dictionary containing the required changes to the attributes.
            Default is None.
        max_lead_time (int):
            Maximum lead time required (mins).
            Default is 360.
        lead_time_interval (int):
            Interval between required lead times (mins).
            Default is 15.
        accumulation_fidelity (int):
            If set, this will additionally return accumulations calculated
            from the advected fields. This fidelity specifies the time
            interval in minutes between advected fields that is used to
            calculate these accumulations. This interval must be a factor of
            the lead_time_interval.
            Default is 0.

    Returns:
        iris.cube.CubeList:
            New cubes with updated time and extrapolated data.

    Raises:
        ValueError:
            can either use s_cube and d_cube or u_cube and v_cube.
            Therefore: (s and d)⊕(u and v)
        ValueError:
            If accumulation_fidelity is greater than 0 and max_lead_time is not
            cleanly divisible by accumulation_fidelity.
    """
    if (speed_cube and direction_cube) and not (u_cube or v_cube):
        u_cube, v_cube = ResolveWindComponents().process(
            speed_cube, direction_cube)
    elif u_cube and v_cube and not (speed_cube or direction_cube):
        pass
    else:
        raise ValueError('Cannot mix advection component velocities with speed'
                         ' and direction')

    # determine whether accumulations are also to be returned, and modify time
    # interval if finer intervals are needed for accumulations
    time_interval = lead_time_interval
    if accumulation_fidelity > 0:
        fraction, _ = np.modf(max_lead_time / accumulation_fidelity)
        if fraction != 0:
            msg = ("The specified lead_time_interval ({}) is not cleanly "
                   "divisible by the specified accumulation_fidelity ({}). As "
                   "a result the lead_time_interval cannot be constructed from"
                   " accumulation cubes at this fidelity.")
            raise ValueError(msg.format(lead_time_interval,
                                        accumulation_fidelity))
        time_interval = accumulation_fidelity

    # extrapolate input data to required lead times
    forecast_plugin = CreateExtrapolationForecast(
        input_cube, u_cube, v_cube,
        orographic_enhancement_cube=orographic_enhancement_cube,
        attributes_dict=attributes_dict)
    forecast_cubes = forecast_plugin.process(time_interval, max_lead_time)

    # filter out rate forecasts that are not required
    lead_time_filter = lead_time_interval // time_interval
    forecast_to_return = forecast_cubes[::lead_time_filter].copy()
    for i in forecast_cubes:
        print(i.attributes.pop('history'))
    return CubeList(forecast_to_return).merge_cube()


if __name__ == "__main__":
    main()
