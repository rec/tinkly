"""Describe tinkly's generated endpoint properties during static API analysis."""

import ast

import griffe


class EndpointProperties(griffe.Extension):
    """Recognize getter and setter declarations on TwinklyClient."""

    def on_attribute_instance(
        self,
        *,
        node: ast.AST | griffe.ObjectNode,
        attr: griffe.Attribute,
        **kwargs: object,
    ) -> None:
        """Add property labels, response types, and HTTP behavior to factory calls.

        Only assignments on tinkly.client.TwinklyClient are processed. Preserve
        any endpoint-specific attribute docstring after the generated details.
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
        description = (
            f'HTTP endpoint `GET {path}`.\n\n'
            'Each read sends a fresh request and returns a '
            '`tinkly.client.TwinklyResponse` containing `http_status` and `data`.\n\n'
            f'Authentication is {"required" if authenticated else "not required"}.'
        )
        if writable:
            description += (
                f'\n\nAssign a `dict[str, object]` JSON body to send `POST {path}`. '
                'Assignment does not return the response; use `post()` when needed.'
            )
        else:
            description += '\n\nThis property is read-only.'
        description += '\n\nRequest errors propagate to the caller.'
        if attr.docstring is not None:
            description += f'\n\n{attr.docstring.value}'

        attr.labels.difference_update({'class-attribute', 'instance-attribute'})
        attr.labels.add('property')
        if writable:
            attr.labels.add('writable')
        attr.annotation = griffe.ExprName('TwinklyResponse', parent=attr.parent)
        attr.value = None
        attr.docstring = griffe.Docstring(description, parent=attr)
