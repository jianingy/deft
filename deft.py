# -*- coding: utf-8 -*-
#
# Copyright 2015, Jianing Yang
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#
# Author: Jianing Yang <jianingy.yang@gmail.com>

# TODOs:
# XXX: YAML Syntax Precheck

from contextlib import contextmanager
from json import dumps as json_encode
from os.path import isdir, splitext, join as path_join
from prettytable import PrettyTable
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from subprocess import call
from tempfile import NamedTemporaryFile
from textwrap import wrap as wrap_text
from yaml import load as yaml_load, safe_dump as yaml_dump
from yaml.parser import ParserError as YAMLParserError
from yaml.scanner import ScannerError as YAMLScannerError

import argparse
import pkg_resources
import sqlalchemy.exc as sqlexc
import sys
import os

__project__ = 'deft'
__version__ = pkg_resources.require(__project__)[0].version


class GenericError(Exception):

    message = 'an error occurred'

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if not message:
            message = self.message % kwargs

        super(GenericError, self).__init__(message)


class ConfigurationError(GenericError):
    pass


class OptionError(GenericError):
    pass


class ViewNotFoundError(GenericError):
    message = 'view %(label)s cannot be found'


class FormNotFoundError(GenericError):
    message = 'form %(label)s cannot be found'


class EditError(GenericError):
    original_exception = None


def warn(s):
    print >>sys.stderr, "WARN:", s


def error(s):
    print >>sys.stderr, "ERROR:", s


def fatal(s, code=111):
    print >>sys.stderr, "FATAL:", s
    sys.exit(code)


def build_recipe_map(opts):

    found = filter(lambda x: isdir(x),
                   (opts.recipe, 'deft-config',
                    '~/.deft/config', '/etc/deft/config'))

    if not found:
        raise ConfigurationError('cannot find configuration directory')

    coll = []
    recipe = found[0]
    for root, dirs, files in os.walk(recipe):
        norm = lambda x: x[len(recipe):]
        mkclass = lambda x: x.split('/')[1]
        mklabel = lambda x: '.'.join(splitext(x)[0].split('/')[2:])
        is_yaml = lambda x: splitext(x)[1] == '.yaml'
        coll.extend(map(lambda x: (mkclass(norm(x)), mklabel(norm(x)), x),
                        map(lambda x: path_join(root, x),
                            filter(is_yaml, files))))

    rmap = dict(views=dict(), forms=dict(), sources=dict())
    for klass, label, path in coll:
        if klass not in rmap:
            warn("ignore unsupport config `%s'" % path)
            continue
        assert(label not in rmap[klass])
        rmap[klass][label] = path

    return rmap


def edit(draft, opts, initial=''):
    editor = os.environ.get('EDITOR', 'vim')
    draft.flush()
    written = os.fstat(draft.fileno()).st_size
    if initial and written == 0:
        draft.write(initial.encode('UTF-8'))
        draft.flush()
    status = call([editor, draft.name])
    draft.seek(0, 0)
    reviewed = draft.read()
    return (status, reviewed)


def edit_form(draft, rmap, opts):
    if opts.label not in rmap['forms']:
        raise FormNotFoundError(label=opts.label)

    with open(rmap['forms'][opts.label]) as y:
        spec = yaml_load(y)

    writables = map(lambda x: x['name'],
                    filter(lambda x: x.get('writable', False),
                           spec['columns']))

    with open_datasource(rmap, spec['source']) as db:
        comment = lambda x: '# %s' % x
        row = db.execute(text(spec['detail']), dict(pk=opts.pk)).fetchone()
        initial = []
        if 'comments' in spec:
            wrapped = map(comment, wrap_text(spec['comments'], 78))
            initial.extend(wrapped)
        original = yaml_dump(dict(row), default_flow_style=False).split('\n')
        initial.append("")
        initial.append("# originial values")
        initial.append("# ----------------")
        initial.extend(map(comment, original))
        initial.append("# new values")
        initial.append("# ----------")
        can_edit = dict(filter(lambda x: x[0] in writables, dict(row).items()))
        initial.extend(yaml_dump(can_edit,
                                 default_flow_style=False).split('\n'))
        try:
            status, yaml_str = edit(draft, opts, initial="\n".join(initial))
            reviewed = yaml_load(yaml_str)
            db.execute(text(spec['update']), pk=opts.pk, **reviewed)
        except (YAMLParserError, YAMLScannerError) as e:
            err = EditError('YAML Parsing Error: %s' % str(e))
            err.original_exception = e
            raise err


def list_all_views(rmap):
    t = PrettyTable(['Label', 'Title', 'YAML', 'Description'])
    for label, path in rmap['views'].iteritems():
        with open(path) as y:
            spec = yaml_load(y.read())
        t.add_row([label,
                   spec.get('title', ''),
                   path,
                   spec.get('description', '')])
    print t


@contextmanager
def open_datasource(rmap, name):
    with open(rmap['sources'][name]) as y:
        db_spec = yaml_load(y.read())

    db_uri = ("%(dialect)s+%(driver)s://%(user)s:%(password)s"
              "@%(host)s/%(dbname)s") % db_spec
    engine = create_engine(db_uri)
    conn = engine.connect()
    try:
        yield conn
    except sqlexc.ProgrammingError as e:
        err = unicode(e).split('\n')
        error("SQL Error: %s" % err[0])
    conn.close()


def parse_cli_option():
    base = argparse.ArgumentParser(__project__)
    base.add_argument('--recipe', help='recipe directory')
    cmds = base.add_subparsers(dest='cmd')

    # show command
    cmd_show = cmds.add_parser('show', help='show data of the given view')
    cmd_show.add_argument('--detail', action='store_true',
                          help='show details')
    cmd_show.add_argument('-j', '--json', action='store_true',
                          help='show result in json format')
    cmd_show.add_argument('-f', '--filter',
                          help='filter result')
    cmd_show.add_argument('label', help='name of the view')

    # edit command
    cmd_edit = cmds.add_parser('edit', help='edit given record')
    cmd_edit.add_argument('--pk', required=True,
                          help=('primary key used to find the unique record'))
    cmd_edit.add_argument('label', help='name of the view')

    # list all views
    cmd_list_views = cmds.add_parser('list-views', help='list all views')

    return base.parse_args()


def parse_filter_expr(expr):

    import pyparsing as pp

    wordcount = dict()

    def make_clause(tokens):
        lhs, oper, rhs = tokens[0]
        if oper == '~':
            oper = 'LIKE'
            rhs = '%%%s%%' % rhs
        elif oper == '!~':
            oper = 'NOT LIKE'
            rhs = '%%%s%%' % rhs
        wordcount[lhs] = wordcount.get(lhs, 0) + 1
        name = "%s_%d" % (lhs, wordcount[lhs])
        return "( %s %s :%s )" % (lhs, oper, name), {name: rhs}

    def make_relation(cword):

        def f(inputs):
            tokens, values = zip(*inputs[0])
            whole = reduce(lambda acc, x: acc.update(x) or acc, values, dict())
            return (" %s " % cword).join(tokens), whole
        return f

    ident = pp.Word(pp.alphas, pp.alphanums + '_')
    value = (pp.Word(pp.alphanums + '_' + '-' + '.')
             | pp.quotedString.setParseAction(lambda t: t[0][1:-1]))
    oper = pp.oneOf('!= = !~ ~ >= <= > <')
    cond = pp.Group(ident + oper + value).setParseAction(make_clause)
    cwords = [(pp.Suppress(pp.oneOf(["NOT"], caseless=True)), 1,
               pp.opAssoc.RIGHT, make_relation('NOT')),
              (pp.Suppress(pp.oneOf(["AND", "&&"], caseless=True)), 2,
               pp.opAssoc.LEFT, make_relation('AND')),
              (pp.Suppress(pp.oneOf(["OR", "&&"], caseless=True)), 2,
               pp.opAssoc.LEFT, make_relation('OR'))]
    stmt = pp.operatorPrecedence(cond, cwords)

    try:
        return stmt.parseString(expr, parseAll=True)[0]
    except pp.ParseException as e:
        fatal("filter expression error: %s" % e)


def safe_edit_form(rmap, opts):
    with scratch() as draft:
        while True:
            try:
                edit_form(draft, rmap, opts)
                print "Record updated successfully!"
                return
            except EditError as e:
                print >>sys.stderr, "File Error: %s" % e
                val = raw_input("(A)bort, (R)etry: ").upper()
                if val == 'A':
                    break


@contextmanager
def scratch():
    t = NamedTemporaryFile(mode='w+')
    yield t
    t.close()
    assert not os.path.exists(t.name)


def show_view(rmap, opts):
    if opts.label not in rmap['views']:
        raise ViewNotFoundError(label=opts.label)

    with open(rmap['views'][opts.label]) as y:
        spec = yaml_load(y)

    if opts.detail:
        query = spec['detail'].strip().strip(';')
    else:
        query = spec['list'].strip().strip(';')

    columns = dict(map(lambda x: (x['name'], x), spec['columns']))

    if opts.filter:
        sql, vals = parse_filter_expr(opts.filter)
        unbind = text("SELECT * FROM (%s) as ______ WHERE %s" % (query, sql))
        query = unbind.bindparams(**vals)

    if opts.json:
        with open_datasource(rmap, spec['source']) as db:
            norm = lambda x: dict(map(lambda x: (x[0], unicode(x[1])),
                                      x.items()))
            print json_encode(map(lambda row: dict(norm(row)),
                                  db.execute(query).fetchall()),
                              indent=4)
    else:
        with open_datasource(rmap, spec['source']) as db:
            result = db.execute(query)
            title = lambda x: columns[x].get('title', x)
            rows = result.fetchall()
            if opts.detail:
                for row in rows:
                    t = PrettyTable(['key', 'value'])
                    t.align['key'] = 'r'
                    t.align['value'] = 'l'
                    map(lambda x: t.add_row([title(x) if x in columns else x,
                                             row[x]]), result.keys())
                    print t
                    print
            else:
                headers = map(lambda x: title(x) if x in columns else x,
                              result.keys())
                t = PrettyTable(headers)
                map(lambda row: t.add_row(row), rows)
                print t


def main():
    opts = parse_cli_option()
    rmap = build_recipe_map(opts)

    if opts.cmd == 'show':
        show_view(rmap, opts)
    elif opts.cmd == 'edit':
        safe_edit_form(rmap, opts)
    elif opts.cmd == 'list-views':
        list_all_views(rmap)