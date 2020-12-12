import json

import colander
import deform
import rulez
from inverter import dc2colander
from morpcc.crud.view.edit import edit as default_edit
from morpcc.crud.view.listing import datatable_search
from morpcc.crud.view.listing import listing as default_listing
from morpcc.crud.view.view import view as default_view
from morpfw.crud import permission as crudperm

from ..app import App
from ..application.model import ApplicationModel
from ..validator.refdata import ReferenceDataValidator
from .model import content_collection_factory
from .modelui import EntityContentCollectionUI, EntityContentModelUI


@App.json(model=EntityContentCollectionUI, name="term-search", permission=crudperm.View)
def term_search(context, request):
    value_field = request.GET.get("value_field", "").strip()
    if not value_field:
        return {}
    term_field = request.GET.get("term_field", "").strip()
    if not term_field:
        return {}
    term = request.GET.get("term", "").strip()
    if not term:
        return {}

    col = context.collection
    objs = col.search(query={"field": term_field, "operator": "~", "value": term})
    result = {"results": []}
    for obj in objs:
        result["results"].append({"id": obj[value_field], "text": obj[term_field]})
    return result


@App.html(
    model=EntityContentModelUI,
    name="view",
    template="master/entity/content/view.pt",
    permission=crudperm.View,
)
def content_view(context, request):
    result = default_view(context, request)
    entity = context.model.entity()
    result["entity_name"] = entity["name"]
    result["entity_title"] = entity["title"]
    result["relationships"] = []
    for r, rel in sorted(context.model.relationships().items(), key=lambda x: x[0]):
        relmodel = context.model.resolve_relationship(rel)
        if relmodel:
            colui = EntityContentCollectionUI(request, relmodel.collection)
            relmodelui = EntityContentModelUI(request, relmodel, colui)
            reldata = default_view(relmodelui, request)
            reldata["title"] = rel["title"]
            reldata["context"] = relmodelui
            reldata["content"] = relmodel
            validate_form(
                relmodel, request, reldata["form"],
            )
            result["relationships"].append(reldata)
    result["backrelationships"] = []
    for br, brel in sorted(
        context.model.backrelationships().items(), key=lambda x: x[0]
    ):
        refmodel = brel.reference_relationship().entity()
        columns = []
        column_options = []
        for colname, col in refmodel.effective_attributes().items():
            columns.append(col["title"])
            column_options.append({"name": colname, "orderable": True})
        breldata = {
            "name": brel["name"],
            "uuid": brel["uuid"],
            "title": brel["title"],
            "single_relation": brel["single_relation"] or False,
            "datatable_url": request.link(
                context,
                "backrelationship-search.json?backrelationship_uuid={}".format(
                    brel["uuid"]
                ),
            ),
            "columns": columns,
            "column_options": json.dumps(column_options),
        }

        if brel["single_relation"]:
            content = context.model.resolve_backrelationship(brel)
            if content:
                item = content[0]
                itemui = item.ui()
                formschema = dc2colander.convert(
                    item.schema,
                    request=request,
                    include_fields=itemui.view_include_fields,
                    exclude_fields=itemui.view_exclude_fields,
                    default_tzinfo=request.timezone(),
                )
                fs = formschema()
                fs = fs.bind(context=item, request=request)
                breldata["form"] = deform.Form(fs)
                breldata["form_data"] = item.as_dict()
                breldata["content"] = item
                validate_form(item, request, breldata["form"])
        result["backrelationships"].append(breldata)
    result["backrelationships"] = sorted(
        result["backrelationships"],
        key=lambda x: (0 if x["single_relation"] else 1, x["name"]),
    )

    validate_form(
        context.model, request, result["form"],
    )
    return result


def validate_form(context, request, form):
    form_data = context.validation_dict()
    schema = context.schema
    form_errors = []
    for attrname, attr in schema.__dataclass_fields__.items():
        field_errors = []
        field_value = form_data.get(attrname, None)

        metadata = attr.metadata
        if metadata.get("required", True):
            if form_data.get(attrname, None) is None:
                field_errors.append("Field is required")

        validators = metadata.get("validators", [])
        for validate in validators:
            error_msg = validate(request, schema, attr, field_value)
            if error_msg:
                field_errors.append(error_msg)

        if field_errors and attrname in form:
            field_error = colander.Invalid(form[attrname].widget, field_errors)
            form[attrname].widget.handle_error(form[attrname], field_error)

    for validate in schema.__validators__:
        error_msg = validate(request, schema, form_data)
        if error_msg:
            form_errors.append(error_msg)

    if form_errors:
        form_error = colander.Invalid(form.widget, form_errors)
        form.widget.handle_error(form, form_error)


def _entity_dt_result_render(context, request, columns, objs):
    rows = []
    collection = context.collection
    for o in objs:
        row = []
        formschema = dc2colander.convert(
            collection.schema, request=request, default_tzinfo=request.timezone()
        )
        fs = formschema()
        fs = fs.bind(context=o, request=request)
        form = deform.Form(fs)
        validate_form(o, request, form)
        for c in columns:
            if c["name"].startswith("structure:"):
                row.append(context.get_structure_column(o, request, c["name"]))
            else:
                field = form[c["name"]]
                value = o.data[c["name"]]
                if value is None:
                    value = colander.null
                out = field.render(
                    value, readonly=True, request=request, context=context
                )
                if field.error:
                    for msg in field.error.messages():
                        out += (
                            "<div class='alert alert-danger'>"
                            "<i class='fa fa-exclamation-triangle'></i>"
                            " {}</div>"
                        ).format(msg)
                row.append(out)
        rows.append(row)
    return rows


@App.json(
    model=EntityContentModelUI,
    name="backrelationship-search.json",
    permission=crudperm.View,
)
def relationship_content_search(context, request):
    brel_uuid = request.GET.get("backrelationship_uuid", "").strip()
    if not brel_uuid:
        return {}

    brel = request.get_collection("morpcc.backrelationship").get(brel_uuid)
    rel = brel.reference_relationship()
    attr = rel.reference_attribute()
    collectionui = content_collection_factory(
        brel.reference_entity(), context.model.collection.__application__
    ).ui()

    return datatable_search(
        collectionui,
        request,
        additional_filters=rulez.field[rel["name"]] == context.model[attr["name"]],
        renderer=_entity_dt_result_render,
    )
