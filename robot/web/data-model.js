/* Pure view helpers shared by the browser and hardware-free checks. */
const DatasetView = {
  segments(detail) { return detail.scope === 'session' ? detail.segments : [detail]; },
  series(detail) {
    const segments=this.segments(detail),stride=Math.max(1,Math.ceil(segments.reduce((sum,s)=>sum+s.trajectory.length,0)/9000));
    return segments.map(segment => ({
      id: segment.instance_id || segment.manifest.instance_id,
      rows: segment.trajectory.filter((row,index)=>index%stride===0||index===segment.trajectory.length-1).map(row => [row[0] + (segment.time_offset_s || 0), ...row.slice(1)])
    }));
  },
  nextPlayable(segments, index) {
    for (let next=index+1; next<segments.length; next++) if (segments[next].frame_count>0) return next;
    return -1;
  }
};
if (typeof module !== 'undefined') module.exports = DatasetView;
