import React from "react";

import useMCPProposals
  from "../hooks/useMCPProposals";


function StatusBadge({
  status,
}) {
  return (
    <span
      className={
        `mcp-status ${status}`
      }
    >
      {status}
    </span>
  );
}


export default function MCPRequestsPage() {
  const {
    proposals,
    loading,
    error,
  } = useMCPProposals();

  const pending =
    proposals.filter(
      proposal =>
        proposal.status === "pending"
    );

  return (
    <div className="mcp-page">

      <header className="mcp-page-header">

        <div>
          <span className="mcp-eyebrow">
            BABY / CAPABILITY LAB
          </span>

          <h1>
            MCP Requests
          </h1>

          <p>
            Capabilities suggested by Nemotron
            when Baby does not currently have
            the right local tool.
          </p>
        </div>

        <div className="mcp-summary">
          <span>
            Pending
          </span>

          <strong>
            {pending.length}
          </strong>
        </div>

      </header>

      <div className="mcp-security-note">
        Nemotron may suggest capabilities,
        but it cannot create, install, or
        activate them automatically.
      </div>

      <div className="mcp-scroll-area">

        {loading && (
          <div className="mcp-empty">
            Loading MCP requests...
          </div>
        )}

        {error && (
          <div className="mcp-empty">
            MCP proposal stream is not
            available yet.
          </div>
        )}

        {!loading &&
         !error &&
         proposals.length === 0 && (
          <div className="mcp-empty">

            <div className="mcp-empty-core">
              ◇
            </div>

            <h2>
              No MCP requests
            </h2>

            <p>
              Nemotron has not identified
              any missing Baby capabilities.
            </p>

          </div>
        )}

        <div className="mcp-grid">

          {proposals
            .slice()
            .reverse()
            .map(
              proposal => (
                <article
                  className="mcp-card"
                  key={proposal.id}
                >

                  <div className="mcp-card-top">

                    <div>
                      <span className="mcp-agent">
                        {
                          proposal
                            .suggested_agent
                        }
                      </span>

                      <h2>
                        {proposal.name}
                      </h2>
                    </div>

                    <StatusBadge
                      status={
                        proposal.status
                      }
                    />

                  </div>

                  <p className="mcp-description">
                    {proposal.description}
                  </p>

                  <div className="mcp-section">

                    <span>
                      Why Nemotron requested it
                    </span>

                    <p>
                      {proposal.reason}
                    </p>

                  </div>

                  {proposal.user_request && (
                    <div className="mcp-request">

                      <span>
                        Original Request
                      </span>

                      <p>
                        “
                        {proposal.user_request}
                        ”
                      </p>

                    </div>
                  )}

                  <div className="mcp-meta-grid">

                    <div>
                      <span>
                        Privacy
                      </span>

                      <strong>
                        {proposal.privacy}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Confirmation
                      </span>

                      <strong>
                        {
                          proposal
                            .confirmation_required
                            ? "Required"
                            : "Not required"
                        }
                      </strong>
                    </div>

                  </div>

                  <div className="mcp-section">

                    <span>
                      Inputs
                    </span>

                    <pre>
                      {
                        JSON.stringify(
                          proposal.inputs,
                          null,
                          2
                        )
                      }
                    </pre>

                  </div>

                  <div className="mcp-section">

                    <span>
                      Expected Output
                    </span>

                    <pre>
                      {
                        JSON.stringify(
                          proposal
                            .expected_output,
                          null,
                          2
                        )
                      }
                    </pre>

                  </div>

                  <footer className="mcp-card-footer">

                    <span>
                      {
                        new Date(
                          proposal.created_at
                        ).toLocaleString()
                      }
                    </span>

                    <span>
                      {proposal.id}
                    </span>

                  </footer>

                </article>
              )
            )}

        </div>

      </div>

    </div>
  );
}