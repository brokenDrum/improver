#!/usr/bin/env bats
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

. $IMPROVER_DIR/tests/lib/utils

@test "extrapolate with json file" {
  improver_check_skip_acceptance
  KGO="nowcast-extrapolate/extrapolate/kgo_with_metadata.nc"

  UVCOMP="$IMPROVER_ACC_TEST_DIR/nowcast-optical-flow/basic/kgo.nc"
  INFILE="201811031600_radar_rainrate_composite_UK_regridded.nc"
  JSONFILE="$IMPROVER_ACC_TEST_DIR/nowcast-optical-flow/metadata/precip.json"
  OE1="20181103T1600Z-PT0003H00M-orographic_enhancement.nc"

  # Run processing and check it passes
  run improver nowcast-extrapolate \
    "$IMPROVER_ACC_TEST_DIR/nowcast-optical-flow/basic/$INFILE" \
    "$TEST_DIR/output.nc" \
    --json_file "$JSONFILE" --max_lead_time 30 \
    --u_and_v_filepath "$UVCOMP" \
    --orographic_enhancement_filepaths \
    "$IMPROVER_ACC_TEST_DIR/nowcast-optical-flow/basic/$OE1"
  [[ "$status" -eq 0 ]]

  improver_check_recreate_kgo "output.nc" $KGO

  # Run nccmp to compare the output and kgo.
  improver_compare_output "$TEST_DIR/output.nc" \
      "$IMPROVER_ACC_TEST_DIR/$KGO"
}
