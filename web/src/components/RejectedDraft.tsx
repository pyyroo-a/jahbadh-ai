import type { FeedItem, Rejection } from "../api/types";
import { rejectionStatus } from "../state/evidence";
import { LAYER_LABELS } from "../state/labels";

export default function RejectedDraft({ item, rejection }: { item: FeedItem; rejection: Rejection }) {
  return (
    <div className="rejected">
      <div className="tag">Rejected draft</div>
      <s dir="auto">{rejection.text}</s>
      <div className="rejected-why">
        <span className="bad">✗ {LAYER_LABELS[rejection.layer]}</span> · {rejectionStatus(item, rejection)}
      </div>
      <ul className="reasons">
        {rejection.reasons.map((reason, i) => <li key={i}>{reason}</li>)}
      </ul>
    </div>
  );
}
