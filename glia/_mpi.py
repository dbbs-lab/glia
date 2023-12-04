try:
    import mpi4py.MPI
except ImportError as e:
    _comm = None
    has_mpi = False
    main_node = True
    parallel_run = False
else:
    _comm = mpi4py.MPI.COMM_WORLD
    has_mpi = True
    main_node = not _comm.Get_rank()
    parallel_run = _comm.Get_size() > 1


def set_comm(comm):
    global _comm

    _comm = comm


def barrier():
    if _comm:
        _comm.barrier()


def bcast(data, root=0):
    if not _comm:
        return data
    else:
        return _comm.bcast(data, root=root)
