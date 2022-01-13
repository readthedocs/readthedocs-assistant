from yaml import Dumper

# This list specifies the order in which the keys will appear in the config
# We only care about primary ones, the inner ones will be sorted alphabetically
# TODO: Add one empty line after each config block?
SORTED_KEYS = ["version", "build", "python", "conda", "sphinx", "formats"]


def rtd_key_sorting(item):
    return SORTED_KEYS.index(item[0])


class RTDDumper(Dumper):
    def represent_dict_custom_order(self, data):
        try:
            items = sorted(data.items(), key=rtd_key_sorting)
            return self.represent_dict(items)
        except ValueError:
            # A sub-dictionary from the config
            # Let it be dumped with the usual method
            return super().represent_dict(data)


RTDDumper.add_representer(dict, RTDDumper.represent_dict_custom_order)
