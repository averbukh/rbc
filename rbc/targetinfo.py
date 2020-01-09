import ctypes


class TargetInfo(object):
    """Base class for determining various information about the target
    system.
    """

    def __init__(self, name, strict=False):
        """
        Parameters
        ----------
        name : str
          The name of a target device. Typically 'cpu' or 'gpu'.
        strict: bool
          When True, require that atomic types are concrete. If not,
          raise an exception.
        """
        self.name = name
        self.strict = strict
        self.custom_type_converters = []
        self.info = {}
        self.type_sizeof = {}

    _host_target_info_cache = {}

    @classmethod
    def host(cls, name='host_cpu', strict=False):
        """Return target info for host CPU.
        """
        key = (name, strict)

        target_info = cls._host_target_info_cache.get(key)
        if target_info is not None:
            return target_info

        import llvmlite.binding as ll
        target_info = TargetInfo(name=name, strict=strict)
        target_info.set('name', ll.get_host_cpu_name())
        target_info.set('triple', ll.get_default_triple())
        features = ','.join(['-+'[int(v)] + k
                             for k, v in ll.get_host_cpu_features().items()])
        target_info.set('features', features)

        for tname, ctype in dict(
                bool=ctypes.c_bool,
                size_t=ctypes.c_size_t,
                ssize_t=ctypes.c_ssize_t,
                char=ctypes.c_char,
                uchar=ctypes.c_char,
                schar=ctypes.c_char,
                byte=ctypes.c_byte,
                ubyte=ctypes.c_ubyte,
                wchar=ctypes.c_wchar,
                short=ctypes.c_short,
                ushort=ctypes.c_ushort,
                int=ctypes.c_int,
                uint=ctypes.c_uint,
                long=ctypes.c_long,
                ulong=ctypes.c_ulong,
                longlong=ctypes.c_longlong,
                ulonglong=ctypes.c_ulonglong,
                float=ctypes.c_float,
                double=ctypes.c_double,
                longdouble=ctypes.c_longdouble,
        ).items():
            target_info.type_sizeof[tname] = ctypes.sizeof(ctype)

        cls._host_target_info_cache[key] = target_info
        return target_info

    def set(self, prop, value):
        """Set a target device property to given value.
        """
        supported_keys = ('name', 'triple', 'datalayout', 'features', 'bits',
                          'compute_capability', 'count', 'threads', 'cores')
        if prop not in supported_keys:
            print(f'rbc.{type(self).__name__}:'
                  f' unsupported property {prop}={value}.')
        self.info[prop] = value

    @property
    def triple(self):
        """Return target triple as a string.

        The triple is in a form "<arch>-<vendor>-<os>"
        """
        return self.info['triple']

    @property
    def arch(self):
        """Return architecture string of target device.
        """
        return self.triple.split('-', 1)[0]

    @property
    def bits(self):
        """Return target device address bit-size as int value (32, 64, ...).
        """
        bits = self.info.get('bits')
        if bits is not None:
            return bits
        # expand this dict as needed
        return dict(x86_64=64, nvptx64=64,
                    x86=32, nvptx=32)[self.arch]

    @property
    def datalayout(self):
        """Return LLVM datalayout of target device.
        """
        layout = self.info.get('datalayout')
        if layout is None:
            if self.name != 'cpu':
                print(f'rbc.{type(self).__name__}:'
                      f' no datalayout info for {self.name!r} device')
            # In the following we assume that datalayout of the target
            # host matches with the datalayout of the client host,
            # regardless of what OS these hosts run.
            layout = ''
        return layout

    @property
    def device_features(self):
        """Return a comma-separated string of CPU target features.
        """
        if 'features' in self.info:
            return ','.join(self.info['features'].split())
        return ''

    @property
    def gpu_cc(self):
        """Return compute capabilities (major, minor) of CUDA device target.
        """
        return tuple(map(int, self.info['compute_capability'].split('.')))

    @property
    def device_name(self):
        """Return the name of target device.
        """
        return self.info['name']

    # info may also contain: count, threads, cores

    def sizeof(self, t):
        """Return the sizeof(t) value for given target device.

        Parameters
        ----------
        t : {str, ...}
            Specify types name. For complete support, one should
            implement the sizeof for the following type names: char,
            uchar, schar, byte, ubyte, short, ushort, int, uint, long,
            ulong, longlong, ulonglong, float, double, longdouble,
            complex, bool, size_t, ssize_t. wchar
        """
        s = self.type_sizeof.get(t)
        if s is not None:
            return s
        if isinstance(t, str):
            if t == 'complex':
                return self.sizeof('float') * 2
        if isinstance(t, type) and issubclass(t, ctypes._SimpleCData):
            return ctypes.sizeof(t)
        raise NotImplementedError("%s.sizeof(%r)"
                                  % (type(self).__name__, t))

    def add_converter(self, converter):
        """Add custom type converter.

        Custom type converters are called on non-concrete atomic
        types.

        Parameters
        ----------
        converter : callable
          Specify a function with signature `converter(target_info,
          obj)` that returns `Type` instance corresponding to
          `obj`. If the conversion is unsuccesful, the `converter`
          returns `None` so that other converter functions could be
          tried.

        """
        self.custom_type_converters.append(converter)

    def custom_type(self, t):
        """Return custom type of an object.
        """
        for converter in self.custom_type_converters:
            r = converter(self, t)
            if r is not None:
                return r


# Usage of LocalTargetInfo is deprecated
LocalTargetInfo = TargetInfo.host
