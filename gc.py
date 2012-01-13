#!/usr/bin/python-init -Ot

import gc

def dump_garbage():
    """
    show us what's the garbage about
    """
        
    # force collection
    print "\nGARBAGE:"
    gc.collect()

    print "\nGARBAGE OBJECTS:"
    for x in gc.garbage:
        print "%s\n  %s" % (type(x), str(x)[:80])

if __name__=="__main__":
    import gc
    gc.enable()
    gc.set_debug(gc.DEBUG_LEAK)

    # make a leak
    l = ["adsdaw"]
    l.append(l)
    l.append(l)
    l.pop()
    #l.pop()
    del l

    # show the dirt ;-)
    dump_garbage()
