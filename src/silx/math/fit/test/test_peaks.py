# /*##########################################################################
# Copyright (C) 2016 European Synchrotron Radiation Facility
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ############################################################################*/
"""
Tests for peaks module
"""

import numpy
import pytest

from silx.math.fit import functions
from silx.math.fit import peaks

_PEAK_PARAMETERS = {
    "sum_gauss": (50, 500, 100,
                    50, 600, 80,
                    20, 2000, 100,
                    50, 2250, 110,
                    40, 3000, 99,
                    23, 4980, 80),
    "sum_lorentz": (50, 500, 100,
                    50, 600, 80,
                    20, 2000, 100,
                    50, 2250, 110,
                    40, 3000, 99,
                    23, 4980, 80),
    "sum_pvoigt": (50, 500, 100, 0.4,
                        50, 600, 80, 0.5,
                        20, 2000, 100, 0.6,
                        50, 2250, 110, 0.7,
                        40, 3000, 99, 0.8,
                        23, 4980, 80, 0.3,),
    "sum_splitgauss": (50, 500, 100, 85,
                        50, 600, 80, 110,
                        20, 2000, 100, 100,
                        50, 2250, 110, 99,
                        40, 3000, 99, 110,
                        23, 4980, 80, 80,),
    "sum_splitlorentz": (50, 500, 100, 85,
                        50, 600, 80, 110,
                        20, 2000, 100, 100,
                        50, 2250, 110, 99,
                        40, 3000, 99, 110,
                        23, 4980, 80, 80,),
    "sum_splitpvoigt": (50, 500, 100, 85, 0.4,
                            50, 600, 80, 110, 0.5,
                            20, 2000, 100, 100, 0.6,
                            50, 2250, 110, 99, 0.7,
                            40, 3000, 99, 110, 0.8,
                            23, 4980, 80, 80, 0.3,),
    "sum_splitpvoigt2": (50, 500, 100, 85, 0.4, 0.7,
                            50, 600, 80, 110, 0.5, 0.3,
                            20, 2000, 100, 100, 0.6, 0.4,
                            50, 2250, 110, 99, 0.7, 1,
                            40, 3000, 99, 110, 0.8, 0,
                            23, 4980, 80, 80, 0.3, 0.5,),
    "sum_agauss": (2550, 500, 100,
                    2000, 600, 80,
                    500, 2000, 100,
                    4000, 2250, 110,
                    2300, 3000, 99,
                    3333, 4980, 80),
    "sum_fastagauss": (2550, 500, 100,
                    2000, 600, 80,
                    500, 2000, 100,
                    4000, 2250, 110,
                    2300, 3000, 99,
                    3333, 4980, 80),
    "sum_alorentz": (2550, 500, 100,
                    2000, 600, 80,
                    500, 2000, 100,
                    4000, 2250, 110,
                    2300, 3000, 99,
                    3333, 4980, 80),
    "sum_apvoigt": (500, 500, 100, 0.4,
                        500, 600, 80, 0.5,
                        200, 2000, 100, 0.6,
                        500, 2250, 110, 0.7,
                        400, 3000, 99, 0.8,
                        230, 4980, 80, 0.3,),
    "sum_ahypermet": (1000, 500, 200, 0.2, 100, 0.3, 100, 0.05,
                        1000, 1000, 200, 0.2, 100, 0.3, 100, 0.05,
                        1000, 2000, 200, 0.2, 100, 0.3, 100, 0.05,
                        1000, 2350, 200, 0.2, 100, 0.3, 100, 0.05,
                        1000, 3000, 200, 0.2, 100, 0.3, 100, 0.05,
                        1000, 4900, 200, 0.2, 100, 0.3, 100, 0.05,),
    "sum_fastahypermet": (1000, 500, 200, 0.2, 100, 0.3, 100, 0.05,
                        1000, 1000, 200, 0.2, 100, 0.3, 100, 0.05,
                        1000, 2000, 200, 0.2, 100, 0.3, 100, 0.05,
                        1000, 2350, 200, 0.2, 100, 0.3, 100, 0.05,
                        1000, 3000, 200, 0.2, 100, 0.3, 100, 0.05,
                        1000, 4900, 200, 0.2, 100, 0.3, 100, 0.05,)
}


@pytest.mark.parametrize("peak_profile", list(_PEAK_PARAMETERS))
def test_peak_functions(peak_profile):
    x = numpy.arange(5000)
    peak_params = _PEAK_PARAMETERS[peak_profile]
    func = getattr(functions, peak_profile)

    with pytest.raises(IndexError):
        func(x)
    with pytest.raises(IndexError):
        func(x, *peak_params, 0)

    y = func(x, *peak_params)
    assert x.shape == y.shape


@pytest.mark.parametrize("peak_profile", list(_PEAK_PARAMETERS))
def test_peak_search(peak_profile):
    x = numpy.arange(5000)
    peak_params = _PEAK_PARAMETERS[peak_profile]
    func = getattr(functions, peak_profile)
    y = func(x, *peak_params)
    estimated_peak_params = peaks.peak_search(y=y, fwhm=100, relevance_info=True)

    assert len(estimated_peak_params)==6, "Wrong number of peaks detected"
    for i, (peak_position, *_) in enumerate(estimated_peak_params):
        theoretical_peak_position = peak_params[i*(len(peak_params)//6) + 1]
        assert abs(peak_position - theoretical_peak_position) < 25
