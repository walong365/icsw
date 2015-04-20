# empty query set
class empty_query_set(object):
    def iterator(self):
        raise StopIteration

    def all(self):
        raise StopIteration
