"""Describe tinkly's generated endpoint properties during static API analysis."""

import ast

import griffe


class EndpointProperties(griffe.Extension):
    """Recognize getter and setter declarations on TwinklyClient."""

    def on_module_instance(self, *, mod: griffe.Module, **kwargs: object) -> None:
        """Give the generated package index a useful overview of its modules."""
        if mod.path == 'tinkly':
            mod.docstring = griffe.Docstring(
                'Twinkly protocol API.\n\n'
                'Import the symbols you need from these modules:\n\n'
                '- [HTTP client and settings][tinkly.client]: TwinklyClient, '
                'endpoint properties, authentication tokens, and HTTP responses.\n'
                '- [Device discovery][tinkly.discovery]: find controllers on '
                'the local network.\n'
                '- [RGB frame transmission][tinkly.frame]: validate pixel '
                'buffers and send realtime UDP frames.\n'
                '- [Errors][tinkly.errors]: exceptions raised by protocol '
                'operations.\n'
                '- [Authentication helpers][tinkly.authentication]: MAC address '
                'decoding and challenge-response calculations.',
                parent=mod,
            )

    def on_attribute_instance(
        self,
        *,
        node: ast.AST | griffe.ObjectNode,
        attr: griffe.Attribute,
        **kwargs: object,
    ) -> None:
        """Add property labels, response types, and HTTP behavior to factory calls.

        Only assignments on tinkly.client.TwinklyClient are processed. Preserve
        endpoint-specific descriptions; shared behavior belongs on the class.
        """
        if attr.parent is None or attr.parent.path != 'tinkly.client.TwinklyClient':
            return
        if not isinstance(node, ast.Assign) or not isinstance(
            call := node.value, ast.Call
        ):
            return
        if not isinstance(call.func, ast.Name) or call.func.id not in (
            'getter',
            'setter',
        ):
            return

        path = ast.literal_eval(call.args[0])
        authenticated = next(
            (
                ast.literal_eval(k.value)
                for k in call.keywords
                if k.arg == 'authenticated'
            ),
            True,
        )
        writable = call.func.id == 'setter'
        description = f'`GET {path}`'
        if writable:
            description += f', `POST {path}`'
        description += '.'
        if not authenticated:
            description += ' Authentication is not required.'
        if attr.docstring is not None:
            description = f'{attr.docstring.value}\n\n{description}'

        attr.labels.difference_update({'class-attribute', 'instance-attribute'})
        attr.labels.add('property')
        if writable:
            attr.labels.add('writable')
        attr.annotation = griffe.ExprName('TwinklyResponse', parent=attr.parent)
        attr.value = None
        attr.docstring = griffe.Docstring(description, parent=attr)
