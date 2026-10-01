import { formatLine } from "./format";

/** The sticky detail pane of the selected Recall Gap. */
export default function GapDetail({ gap }) {
  return (
    <section className="rv-detail">
      {gap ? (
        <>
          <div className="rv-line big">{formatLine(gap.path)} …</div>
          <div className="rv-compare">
            <div>
              <div className="rv-label">You played</div>
              {gap.wrong_moves.map((m) => (
                <div key={m.san} className="rv-move bad">
                  {m.san} <span className="rv-muted">×{m.count}</span>
                </div>
              ))}
            </div>
            <div>
              <div className="rv-label">Book</div>
              {gap.book_moves.map((m) => (
                <div key={m} className="rv-move good">
                  {m}
                </div>
              ))}
            </div>
          </div>
        </>
      ) : (
        <p className="rv-muted">Select a Recall Gap</p>
      )}
    </section>
  );
}
