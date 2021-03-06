"""
Autogenerate API endpoints by inspecting python-bitcoinlib's RPC client because
maximum lazy.
"""

from copy import copy

# HACK: view_func is weird
import types

# For using python-bitcoinlib for details about the Bitcoin Core RPC protocol.
import inspect

# For some even more devious trickery involving partially-pre-specified
# function calls.
import functools

# Proxy class is used to get information about accepted parameters. Yeah,
# pretty lame but it works.
from bitcoin.rpc import Proxy

from bitcoin.core import (
    # bytes to little endian hex
    b2lx,

    # little endian hex to bytes
    lx,

    # bytes to hex
    b2x,
)

# because of the interwebs...
from flask import (
    Blueprint,
    request,
    g,
    render_template,
)

api = Blueprint("api", __name__, url_prefix="")

ALLOWED_COMMANDS = [
    # blockchain
    "getbestblockhash",
    "getblock",
    "getblockchaininfo",
    "getblockcount",
    "getblockhash",
    "getchaintips",
    "getdifficulty",
    "getmempoolinfo",

    # network
    "getconnectioncount",
    "getnettotals",
    "getnetworkinfo",
    "getpeerinfo",
    "getinfo",

    # transactions
    "getrawtransaction",
    "decoderawtransaction",
]

# All API endpoints conform to the following template, which can also be used
# to construct valid urls.
API_ENDPOINT_TEMPLATE = "/{command_name}"

# Some of the user-supplied values need to be converted. Use this table to
# determine how to convert values automatically.
CONVERSION_TABLE = {
    # convert to bytes
    "block_hash": lx,
    "txid": lx,
    "verbose": bool,
}

def converter(name, value):
    """
    Convert from user-given values into an acceptable internal type.
    """

    if name in CONVERSION_TABLE.keys():
        return CONVERSION_TABLE[name](value)

def create_api_endpoints(commands=ALLOWED_COMMANDS):
    """
    Automatically generate all API endpoints by (ab)using python-bitcoinlib.
    """

    # Only generate API endpoints for the explicitly whitelisted commands.
    for command in commands:

        # store any additional arguments here
        keyword_arguments = {}

        if command in Proxy.__dict__.keys():
            # get a reference to the function
            rpcfunction = Proxy.__dict__[command]

            # investigate the function signature
            argument_spec = inspect.getargspec(rpcfunction)

            # only look at the arguments
            arguments = argument_spec.args

            # nobody cares about the self
            arguments.remove("self")

            # "self" is never a default value
            defaults = argument_spec.defaults

            # Preserve this information for later when constructing the API
            # endpoints.
            for (argument_index, argument) in enumerate(arguments):
                # Perhaps there are not always default values? Who knows.
                if defaults and len(defaults) > argument_index:
                    some_default = defaults[argument_index]
                else:
                    some_default = None

                keyword_arguments[argument] = some_default

        # Construct an API endpoint that accepts the computed arguments. Begin
        # by constructing the API endpoint uri from the template.

        # endpoint is always based on the command name
        api_uri = API_ENDPOINT_TEMPLATE.format(command_name=command)

        def make_command_endpoint(command, keyword_arguments):
            def some_command_endpoint():
                """
                Autogenerated API endpoint.
                """

                # Allow the defaults or user-passed values to be used.
                params = {}

               # Use request.args to get the user-passed value, otherwise use the
                # default as defined in python-bitcoinlib.
                for (argument_name, default_value) in keyword_arguments.items():
                    value = request.args.get(argument_name, default_value)
                    params[argument_name] = value

                # Get a reference to the command, if any.
                # Exclude "getblock" so that the json result is shown instead
                # of the repr of CBlock.
                if command in Proxy.__dict__.keys() and command != "getblock":
                    callable_function = getattr(g.bitcoin_rpc_client, command)
                    rpc_function = functools.partial(callable_function)

                    params2 = {}
                    for (argument_name, default_value) in keyword_arguments.items():
                        value = request.args.get(argument_name, default_value)
                        possibly_converted_value = converter(argument_name, value)
                        params[argument_name] = possibly_converted_value

                    # Call the RPC service command and pass in all of the given
                    # parameters.
                    results = rpc_function(**params)
                else:
                    #_self = g.bitcoin_rpc_client
                    callable_function = g.bitcoin_rpc_client._call
                    rpc_function = functools.partial(callable_function, command)
                    results = rpc_function(*(list(params.values()) + [True]))

                # That's all, folks.
                return repr(results)
            return some_command_endpoint

        view_func = make_command_endpoint(command, keyword_arguments)
        api.add_url_rule(api_uri, endpoint=command, view_func=view_func, methods=["GET"])

# Always create all the endpoints when importing this module. This will attach
# the endpoints to the blueprint, which can then be attached to flask
# application instances.
create_api_endpoints()

# TODO: convert from the above format to the following format for each
# API command. Unfortunately it seems that there must be a custom template to
# display the relevant content.
@api.route("/")
def index():
    blocks = []

    blockcount = g.bitcoin_rpc_client.getblockcount()

    for block_index in range(0, blockcount):
        blockhash = g.bitcoin_rpc_client.getblockhash(block_index)
        blocks.append({
            "height": block_index,
            "hash": blockhash,
        })

    return render_template("blocks.html", blocks=blocks)
