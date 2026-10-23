"""Serial bounded worker orchestration for the versioned studio extension."""
import subprocess
import sys


def run(manager, jid, mode, backend, studio):
    process = log = None
    failure = None
    code = None
    folder = manager.root/jid
    try:
        with manager.lock:
            folder = manager.jobpath(jid)
            if manager.jobs[jid]['status'] == 'cancelled':
                return
            manager.jobs[jid]['status'] = 'analyzing' if mode == 'analyze' else 'exporting'
            manager.save(jid)
            log = (folder/(mode+'.worker.log')).open('wb')
            process = subprocess.Popen([sys.executable,str(studio/'steady_worker.py'),mode,str(folder)],
                                       stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            manager.processes[jid] = process
        try:
            code = process.wait(timeout=130 if mode == 'analyze' else 250)
        except subprocess.TimeoutExpired:
            manager.stop_process(process)
            failure = 'Studio worker exceeded its outer wall-time limit; no result accepted.'
        error = folder/(mode+'.error.json')
        if error.exists():
            failure = backend.read_json(error).get('message','Studio worker failed.')
        elif code != 0:
            failure = failure or 'Studio worker stopped or exceeded its limit; no result accepted.'
        elif not (folder/('analysis.json' if mode == 'analyze' else 'export.json')).is_file():
            failure = 'Studio worker returned without the required result; no result accepted.'
    except BaseException as error:
        failure = 'Studio worker orchestration failed: '+type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            try:
                manager.stop_process(process)
            except BaseException as error:
                failure = failure or 'Studio worker cleanup failed: '+str(error)
        if log is not None:
            log.close()
        with manager.lock:
            manager.processes.pop(jid,None)
            if jid in manager.jobs and manager.jobs[jid]['status'] != 'cancelled':
                if failure:
                    manager.jobs[jid].update(status='failed',error=failure)
                else:
                    manager.jobs[jid]['status'] = 'review' if mode == 'analyze' else 'complete'
            if jid in manager.jobs:
                try:
                    manager.save(jid)
                except OSError as error:
                    manager.jobs[jid].update(status='failed',error='Cannot persist studio job state: '+str(error))
