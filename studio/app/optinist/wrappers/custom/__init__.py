from studio.app.optinist.wrappers.custom.custom_node import my_function

custom_wrapper_dict = {
    "custom_node": {
        "template": {
            "function": my_function,
            "conda_name": "custom",
        },
    }
}
