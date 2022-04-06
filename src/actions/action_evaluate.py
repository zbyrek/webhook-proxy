from actions import action, Action

# TODO: Remove action (same as log)


@action('eval')
class EvaluateAction(Action):
    def __init__(self, block):
        self.block = block

    def _run(self):
        print(self._render_with_template(self.block))
