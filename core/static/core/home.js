document.addEventListener("DOMContentLoaded", () => {
    const cards = Array.from(document.querySelectorAll(".module-card"));

    if (!cards.length) {
        return;
    }

    const movementMap = {
        anime: {
            ArrowDown: "games",
            ArrowRight: "hibi",
        },
        games: {
            ArrowUp: "anime",
            ArrowRight: "hibi",
        },
        hibi: {
            ArrowLeft: "anime",
            ArrowRight: "watchroom",
        },
        watchroom: {
            ArrowDown: "music",
            ArrowLeft: "hibi",
        },
        music: {
            ArrowUp: "watchroom",
            ArrowLeft: "hibi",
        },
    };

    cards.forEach((card) => {
        const status = card.querySelector(".module-status");

        if (status) {
            status.dataset.originalLabel = status.textContent.trim();
            status.dataset.wasSoon = status.classList.contains(
                "module-status--soon"
            )
                ? "true"
                : "false";
        }
    });

    let selectedCard = null;

    function updateStatus(card, selected) {
        const status = card.querySelector(".module-status");

        if (!status) {
            return;
        }

        if (selected) {
            const comingSoon =
                status.dataset.originalLabel.toLowerCase() === "coming soon";

            status.textContent = comingSoon
                ? "Selected · Soon"
                : "Selected";

            status.classList.remove("module-status--soon");
            status.classList.add("module-status--selected");

            return;
        }

        status.textContent = status.dataset.originalLabel;

        status.classList.remove("module-status--selected");
        status.classList.toggle(
            "module-status--soon",
            status.dataset.wasSoon === "true"
        );
    }

    function selectCard(card, focus = false) {
        if (!card || card === selectedCard) {
            return;
        }

        cards.forEach((item) => {
            const isSelected = item === card;

            item.classList.toggle(
                "module-card--selected",
                isSelected
            );

            updateStatus(item, isSelected);
        });

        selectedCard = card;

        if (focus) {
            card.focus({
                preventScroll: true,
            });
        }
    }

    function clearSelection() {
        cards.forEach((card) => {
            card.classList.remove("module-card--selected");
            updateStatus(card, false);
        });

        selectedCard = null;
    }

    cards.forEach((card) => {
        card.addEventListener("mouseenter", () => {
            selectCard(card);
        });

        card.addEventListener("focus", () => {
            selectCard(card);
        });
    });

    cards.forEach((card) => {
        updateStatus(card, card === selectedCard);
    });

    const moduleGrid = document.querySelector(".module-grid");

    moduleGrid?.addEventListener("mouseleave", () => {
        clearSelection();
    });

    document.addEventListener("click", (event) => {
        if (!event.target.closest(".module-card")) {
            clearSelection();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (!window.matchMedia("(min-width: 1100px)").matches) {
            return;
        }

        const target = event.target;

        if (
            target instanceof HTMLInputElement ||
            target instanceof HTMLTextAreaElement ||
            target instanceof HTMLButtonElement
        ) {
            return;
        }

        if (event.key === "Enter") {
            if (
                selectedCard instanceof HTMLAnchorElement &&
                selectedCard.href
            ) {
                selectedCard.click();
            }

            return;
        }

        if (!selectedCard) {
            const firstCard = cards.find(
                (card) => card.dataset.module === "anime"
            );

            if (firstCard) {
                selectCard(firstCard, true);
            }

            return;
        }

        const currentModule = selectedCard.dataset.module;
        const destination =
            movementMap[currentModule]?.[event.key];

        if (!destination) {
            return;
        }

        const destinationCard = cards.find(
            (card) => card.dataset.module === destination
        );

        if (!destinationCard) {
            return;
        }

        event.preventDefault();

        selectCard(destinationCard, true);
    });
});