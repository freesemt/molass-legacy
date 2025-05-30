# coding: utf-8
"""
    SharedArray.py

    Copyright (c) 2019, SAXS Team, KEK-PF
"""
import copy
import numpy as np

# from multiprocessing.shared_memory import SharedMemory
from OurMultiprocessing import SharedMemory
# from molass_legacy.KekLib.OurMmap import SharedMemory

NBYTES_FLOAT64 = 8

class SharedArray:
    def __init__(self, array=None, tuple_=None, name=None):
        if array is None:
            assert tuple_ is not None
            name, shape, dtype = tuple_
            size = np.prod(shape) * NBYTES_FLOAT64
            existing_shm = SharedMemory(name=name, size=size)
            sh_array = np.ndarray(shape, dtype=dtype, buffer=existing_shm.buf)
            self.tuple_ = tuple_
            self.shm = existing_shm
            # deepcopy as a temporary fix to a suspected bug as of Python 3.8.0 + numpy 1.17.4 + matplotlib 3.1.2
            # self.sh_array = copy.deepcopy(sh_array)
            self.sh_array = sh_array
        else:
            shm = SharedMemory(create=True, size=array.nbytes)
            name = shm.name
            sh_array = np.ndarray(array.shape, dtype=array.dtype, buffer=shm.buf)
            sh_array[:] = array[:]  # Copy the original data into shared memory
            self.tuple_ = (name, array.shape, array.dtype)
            self.shm = shm
            self.sh_array = sh_array

    def get_array(self):
        return self.sh_array

    def get_tuple(self):
        return self.tuple_
