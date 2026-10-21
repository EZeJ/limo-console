"""Recording health reporting is independent of the motion gate."""
def recording_problem(state,age):
    if not state.get('active'):return ''
    if age>.75:return 'Recording service is unavailable'
    if not state.get('ready'):return state.get('error') or 'Active recording is not ready'
    return ''
