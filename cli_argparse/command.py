# -*- coding: utf-8 -*-

import argparse
import os
import sys
from collections import OrderedDict

from odoo import (
    api, exceptions,
    registry, service, tools, SUPERUSER_ID)


class CommandMixin(object):
    _parser = None
    _odoo_args = (
        '--db_host',
        '--db_port',
        '--db_name',
        '--db_user',
        '--db_password',
        '--log-level')
    command_args = (
        ('--database', '-d',
         (('dest', 'dbname'),
          ('type', str))), )

    @property
    def parser(self):
        if self._parser is None:
            self._parser = argparse.ArgumentParser(
                prog=(
                    "%s %s"
                    % (sys.argv[0].split(os.path.sep)[-1],
                       self.name)),
                description=self.__doc__)
            self.add_arguments(self._parser)
        return self._parser

    def add_arguments(self, parser, command_args=None):
        command_args = (
            self.command_args
            if command_args is None
            else command_args)
        for arg in command_args:
            if isinstance(arg[-1], tuple):
                args = arg[:-1]
                kwargs = dict(arg[-1])
            else:
                args = arg
                kwargs = {}
            parser.add_argument(*args, **kwargs)

    def parse_args(self, args):
        odoo_args, args = self._extract_odoo_args(args)
        args, remaining = self.parser.parse_known_args(args)
        return args, self._append_odoo_args(remaining, odoo_args)

    def run(self, args):
        service.server.start(preload=[], stop=True)
        args, remaining = self.parse_args(args)
        tools.config.parse_config(remaining)
        self._run_with_env(args)

    def _append_odoo_args(self, args, odoo_args):
        return (
            args
            + [v for k
               in odoo_args.items()
               for v in k])

    def _extract_odoo_args(self, args):
        # this could be done a little more elegantly
        odoo_args = []
        while 1:
            if len(args) > 1 and args[-2] in self._odoo_args:
                v = args.pop()
                k = args.pop()
                odoo_args.append((k, v))
            else:
                break
        return OrderedDict(reversed(odoo_args)), args

    def _run_with_env(self, parsed=None):
        if not getattr(parsed, 'dbname', None):
            self.run_cmd(None, parsed)
            return
        with api.Environment.manage():
            with registry(parsed.dbname).cursor() as cr:
                uid = SUPERUSER_ID
                ctx = api.Environment(
                    cr, uid, {})['res.users'].context_get()
                env = api.Environment(cr, uid, ctx)
                self.run_cmd(env, parsed)
                cr.rollback()


class SubcommandsMixin(CommandMixin):
    command_args = (
        CommandMixin.command_args
        + (('subcommand', ), ))
    subcommand_args = ()

    def parse_args(self, args):
        odoo_args, args = self._extract_odoo_args(args)
        args, remaining = self.parser.parse_known_args(args)
        if args.subcommand:
            _args, remaining = self.parse_subcommand_args(
                args.subcommand, remaining)
            args.__dict__.update(_args.__dict__)
        return args, self._append_odoo_args(remaining, odoo_args)

    def parse_subcommand_args(self, subcommand, args):
        subparser = argparse.ArgumentParser()
        subcommand_args = dict(
            self.subcommand_args).get(subcommand, ())
        self.add_arguments(subparser, subcommand_args)
        return subparser.parse_known_args(args)

    def run_cmd(self, env, parsed):
        try:
            command = getattr(
                self,
                ("run_%s"
                 % parsed.subcommand.replace('-', '_')))
        except AttributeError:
            raise exceptions.Warning(
                "Unrecognized command: %s"
                % parsed.subcommand)
        return command(env, parsed)
