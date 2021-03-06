import morpfw
from morpcc.authn import Identity

from ..index.schema import IndexRecordSchema
from .modelui import ActivityLogCollectionUI, ActivityLogModelUI
from .schema import ActivityLogSchema

#


class ActivityLogModel(morpfw.Model):
    schema = ActivityLogSchema

    #
    def ui(self):
        return ActivityLogModelUI(self.request, self, self.collection.ui())


#


class ActivityLogCollection(morpfw.Collection):
    schema = ActivityLogSchema

    #
    def ui(self):
        return ActivityLogCollectionUI(self.request, self)

    #

    def log(self, context, activity):
        if isinstance(context, ActivityLogModel):
            return
        if issubclass(context.schema, IndexRecordSchema):
            return
        request = self.request
        if isinstance(request.identity, Identity):
            userid = request.identity.userid
        else:
            userid = None

        link = self.request.metalink(
            context
        )
        self.create(
            {
                "userid": userid,
                "metalink_type": link["type"],
                "metalink": link,
                "activity": activity,
                "source_ip": request.client_addr,
                "request_url": request.url,
                'request_method': request.method
            }
        )
