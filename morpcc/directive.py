import dectate
from morepath.directive import SettingAction
from .portletregistry import PortletRegistry

PORTLET_FACTORY_IDS: dict = {}


class PortletFactoryAction(dectate.Action):

    config = {
        'portlet_registry': PortletRegistry
    }

    depends = [SettingAction]

    filter_convert = {
        'under': dectate.convert_dotted_name,
        'over': dectate.convert_dotted_name
    }

    def __init__(self, provider, template=None, under=None, over=None, name=None):
        PORTLET_FACTORY_IDS.setdefault(provider, 0)
        if name is None:
            name = u'portlet_factory_%s_%s' % (
                provider, PORTLET_FACTORY_IDS[provider])
            PORTLET_FACTORY_IDS[provider] += 1
        self.provider = provider
        self.template = template
        self.under = under
        self.over = over
        self.name = name

    def identifier(self, portlet_registry: PortletRegistry):
        return self.name

    def perform(self, obj, portlet_registry: PortletRegistry):
        portlet_registry.register_portlet_factory(
            obj, provider=self.provider,
            template=self.template,
            over=self.over,
            under=self.under
        )
