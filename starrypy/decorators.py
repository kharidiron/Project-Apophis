class EventHook:
    """
    A decorator to point out to the plugin manager which classes are event hooks, and for what event, along with
    sorting priority. Otherwise doesn't do anything by itself.
    """

    def __init__(self, event, priority=0):
        self.event = event
        self.priority = priority

    def __call__(self, f):
        f.event = self.event
        f.priority = self.priority
        return f
