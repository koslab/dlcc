import re

import rulez

from ..referencedata.path import get_collection as get_refdata_collection
from ..referencedatakey.path import get_collection as get_refdatakey_collection


class ReferenceDataValidator(object):
    def __init__(self, referencedata_name, referencedata_property):
        self.referencedata_name = referencedata_name
        self.referencedata_property = referencedata_property

    def __call__(self, request, schema, field, value, mode=None):
        resource = self.get_resource(request, value)
        if not resource:
            return "Invalid reference : {}".format(value)

    def get_resource(self, request, identifier):
        col = get_refdata_collection(request)
        refdatas = col.search(rulez.field["name"] == self.referencedata_name)
        if not refdatas:
            return None
        refdata = refdatas[0]

        keycol = get_refdatakey_collection(request)
        keys = keycol.search(
            rulez.and_(
                rulez.field["referencedata_uuid"] == refdata.uuid,
                rulez.field["name"] == identifier,
            )
        )
        if not keys:
            return None
        return keys[0]
