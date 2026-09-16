from dataclasses import dataclass


@dataclass
class PositionSizeResult:

    account_size: float

    risk_percent: float

    maximum_loss: float

    entry_price: float

    stop_price: float

    risk_per_share: float

    shares: int

    position_value: float

    portfolio_percentage: float

    capped: bool

    warning: str | None


class PositionSizingEngine:

    def calculate(
        self,
        account_size: float,
        entry_price: float,
        stop_price: float,
        risk_percent: float = 0.5,
        max_position_percent: float = 10,
    ):

        if account_size <= 0:
            raise ValueError(
                "Account size must be positive."
            )

        if entry_price <= 0:
            raise ValueError(
                "Entry price must be positive."
            )

        if stop_price >= entry_price:
            raise ValueError(
                "Stop must be below entry price "
                "for a long position."
            )

        risk_per_share = (
            entry_price
            - stop_price
        )

        maximum_loss = (
            account_size
            * risk_percent
            / 100
        )

        shares_by_risk = int(
            maximum_loss
            / risk_per_share
        )

        maximum_position_value = (
            account_size
            * max_position_percent
            / 100
        )

        shares_by_position = int(
            maximum_position_value
            / entry_price
        )

        shares = min(
            shares_by_risk,
            shares_by_position,
        )

        capped = (
            shares_by_position
            < shares_by_risk
        )

        position_value = (
            shares
            * entry_price
        )

        portfolio_percentage = (
            position_value
            / account_size
            * 100
        )

        warning = None

        if shares <= 0:

            warning = (
                "Position is too risky for "
                "the specified account and stop."
            )

        return PositionSizeResult(
            account_size=account_size,

            risk_percent=risk_percent,

            maximum_loss=round(
                maximum_loss,
                2,
            ),

            entry_price=round(
                entry_price,
                2,
            ),

            stop_price=round(
                stop_price,
                2,
            ),

            risk_per_share=round(
                risk_per_share,
                2,
            ),

            shares=shares,

            position_value=round(
                position_value,
                2,
            ),

            portfolio_percentage=round(
                portfolio_percentage,
                2,
            ),

            capped=capped,

            warning=warning,
        )