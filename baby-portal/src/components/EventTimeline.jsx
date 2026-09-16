import { formatEventName } from "../utils/formatEvent";
export default function EventTimeline({ events }) {
    const clean = events.slice(-8).reverse();

    return (
        <div>
            <h2>Event Stream</h2>

            <div className="timeline-list">
                {clean.map((event, index) => {
                    const time = new Date(event.timestamp).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                    });

                    return (
                        <div className="timeline-card" key={index}>
                            <span>{time}</span>
                            <strong>{formatEventName(event.type)}</strong>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}