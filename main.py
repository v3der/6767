
            message = await channel.fetch_message(
                saved_id
            )

            if (
                message
                and bot.user
                and message.author.id == bot.user.id
            ):

                print(
                    "[TICKET PANEL] Panel już istnieje."
                )

                return

        except discord.NotFound:

            # Zapisany panel naprawdę nie istnieje — można utworzyć nowy.
            pass

        except discord.HTTPException as e:

            # Przy 429 lub innym błędzie API NIE wysyłamy kolejnego panelu.
            # Wcześniej wyjątek był ignorowany, co mogło powodować kolejne
            # zapytania i duplikowanie paneli przy każdym reconnectcie.
            print(
                f"[TICKET PANEL] Nie udało się sprawdzić panelu: {e}. "
                "Pomijam tworzenie nowego panelu."
            )
            return

    # =====================================================
    # NOWY PANEL
    # =====================================================

    try:
        message = await channel.send(
            view=TicketPanelView()
        )
    except discord.HTTPException as e:
        print(f"[TICKET PANEL] Nie udało się utworzyć panelu: {e}")
        return

    save_panel_message_id(
        message.id
    )

    print(
        f"[TICKET PANEL] Utworzono panel: "
        f"{message.id}"
    )


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    global views_registered, setup_complete

    print(
        f"Zalogowano jako {bot.user} "
        f"(ID: {bot.user.id})"
    )

    # on_ready może uruchomić się ponownie po reconnectcie.
    # Nie wykonujemy wtedy ponownie konfiguracji i zapytań REST.
    if setup_complete:
        print("[READY] Konfiguracja była już wykonana — pomijam.")
        return

    # Persistent views rejestrujemy tylko raz na proces.
    if not views_registered:
        bot.add_view(TicketPanelView())
        bot.add_view(
            TicketActionView(
                ticket_type="inne",
                owner_mention="@user",
                category_name="Inne"
            )
        )
        views_registered = True

    try:
        await set_bot_status()
        await ensure_ticket_panel()
    except discord.HTTPException as e:
        print(f"[READY] Błąd Discord API podczas konfiguracji: {e}")
    except Exception as e:
        print(f"[READY] Nieoczekiwany błąd konfiguracji: {e}")
    finally:
        # Zapobiega ponawianiu tych samych operacji przy reconnectach.
        setup_complete = True

    print("Bot jest gotowy.")


# =========================================================
# START
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot Discord działa!", 200


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    server = Thread(target=run_web, daemon=True)
    server.start()


keep_alive()


if __name__ == "__main__":
