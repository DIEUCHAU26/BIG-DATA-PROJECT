
def patch_threadpoolctl():
    try:
        from threadpoolctl import ThreadpoolController

        goc = ThreadpoolController._make_controller_from_path
        if getattr(goc, "_an_toan", False):
            return

        def an_toan(self, filepath):
            try:
                return goc(self, filepath)
            except OSError: 
                return None

        an_toan._an_toan = True
        ThreadpoolController._make_controller_from_path = an_toan
    except Exception:
        pass  
