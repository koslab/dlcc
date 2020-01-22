import re
import rulez
import json
import html
import morepath
from ..model import CollectionUI, ModelUI
from ...app import App
from boolean.boolean import ParseError
from ...permission import ViewHome
from ...util import dataclass_to_colander
import colander
import deform
from morpfw.crud import permission as crudperms
import typing

@App.html(model=CollectionUI, name='listing', template='master/crud/listing.pt',
          permission=crudperms.Search)
def listing(context, request):
    column_options = []
    columns = []
    for c in context.columns:
        columns.append(c['title'])
        sortable = True
        if c['name'].startswith('structure:'):
            sortable = False
        column_options.append({
            'name': c['name'],
            'orderable': sortable
        })
    return {
        'page_title': context.page_title,
        'listing_title': context.listing_title,
        'columns': columns,
        'column_options': json.dumps(column_options)
    }


column_pattern = re.compile(r'^columns\[(\d+)\]\[(\w+)\]$')
search_column_pattern = re.compile(r'^columns\[(\d+)\]\[(\w+)\]\[(\w+)\]$')
search_pattern = re.compile(r'^search\[(\w+)\]$')
order_pattern = re.compile(r'order\[(\d+)\]\[(\w+)\]')


def _parse_dtdata(data):
    result = {}

    result['columns'] = []
    result['search'] = {}
    result['order'] = {}
    result['length'] = None
    result['start'] = 0
    result['draw'] = 1
    result['filter'] = None

    columns = [(k, v) for k, v in data if k.startswith('columns')]
    orders = [(k, v) for k, v in data if k.startswith('order')]
    mfilter = [(k, v) for k, v in data if k == 'filter']
    mfilter = mfilter[0][1] if mfilter else None

    column_data = {}
    for k, v in columns:
        m1 = column_pattern.match(k)
        m2 = search_column_pattern.match(k)
        if m1:
            i, o = m1.groups()
            column_data.setdefault(int(i), {})
            column_data[int(i)][o] = v
        elif m2:
            i, o, s = m2.groups()
            column_data.setdefault(int(i), {})
            column_data[int(i)].setdefault(o, {})
            column_data[int(i)][o][s] = v

    result['columns'] = []
    for k in sorted(column_data.keys()):
        result['columns'].append(column_data[k])

    order_data = {}
    for k, v in orders:
        i, o = order_pattern.match(k).groups()
        order_data.setdefault(int(i), {})
        if o == 'column':
            order_data[int(i)][o] = int(v)
        else:
            order_data[int(i)][o] = v

    result['order'] = []
    for k in sorted(order_data.keys()):
        result['order'].append(order_data[k])

    for k, v in data:
        if k == 'draw':
            result['draw'] = int(v)
        elif k == '_':
            result['_'] = v
        elif k == 'start':
            result['start'] = int(v)
        elif k == 'length':
            result['length'] = int(v)
        elif k.startswith('search'):
            i = search_pattern.match(k).groups()[0]
            result['search'].setdefault(i, {})
            result['search'][i] = v

    if mfilter:
        result['filter'] = rulez.parse_dsl(mfilter)
        
    return result


@App.json(model=CollectionUI, name='datatable.json', permission=crudperms.View)
def datatable(context, request):
    collection = context.collection
    data = list(request.GET.items())
    data = _parse_dtdata(data)
    search = []
    if data['search'] and data['search']['value']:
        for fn, field in context.collection.schema.__dataclass_fields__.items():
            if field.type == str:
                search.append({'field': fn,
                                'operator': '~',
                                'value': data['search']['value']})
            if field.type.__origin__ == typing.Union:
                if str in field.type.__args__:
                    search.append({'field': fn,
                                'operator': '~',
                                'value': data['search']['value']})   
        if search:
            search = rulez.or_(*search)
        else:
            search = None

    if data['filter']:
        if search:
            rulez.and_(data['filter'], search)
        else:
            search = data['filter']

    order_by = None
    if data['order']:
        colidx = data['order'][0]['column']
        order_col = data['columns'][colidx]['name']
        if order_col.startswith('structure:'):
            order_by = None
        else:
            order_by = (order_col, data['order'][0]['dir'])
    try:
        objs = collection.search(
            query=search, limit=data['length'], offset=data['start'], order_by=order_by)
    except NotImplementedError:
        objs = collection.search(
            limit=data['length'], offset=data['start'], order_by=order_by)
    total = collection.aggregate(query=data['filter'],
        group={'count': {'function': 'count', 'field': 'uuid'}})
    try:
        total_filtered = collection.aggregate(
            query=search,
            group={'count': {'function': 'count', 'field': 'uuid'}})
    except NotImplementedError:
        total_filtered = total
    rows = []
    for o in objs:
        row = []
        jsonobj = o.data.as_json()
        for c in data['columns']:
            if c['name'].startswith('structure:'):
                row.append(context.get_structure_column(o, request, c['name']))
            else:
                if jsonobj[c['name']] is 0:
                    row.append(str(jsonobj[c['name']]))
                else:
                    row.append(html.escape(str(jsonobj[c['name']] or '')))
        rows.append(row)
    return {
        'draw': data['draw'],
        'recordsTotal': total[0]['count'],
        'recordsFiltered': total_filtered[0]['count'],
        'data': rows
    }
