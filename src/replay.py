"""Convenience entry point for cached human-gold scoring."""
from workflow import main
if __name__=='__main__':
    import sys
    sys.argv.insert(1,'score')
    main()
