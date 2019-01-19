from main.models import *
from main.universals import get_response, configure_logging, safe_getter
from main.dynamic_telegraph_page_creator import DynamicTelegraphPageCreator
from django.utils import timezone
from time import sleep
from datetime import datetime
import logging

# configure_logging()


def participant_answering(participant, participant_group, problem, variant):
    is_right = False
    variant = variant.lower()
    try:
        group_specific_participant_data = participant.groupspecificparticipantdata_set.get(
            participant_group=participant_group)
    except GroupSpecificParticipantData.DoesNotExist:
        group_specific_participant_data = GroupSpecificParticipantData(
            **{
                "participant": participant,
                "group": participant_group,
                "score": 0
            })
        group_specific_participant_data.save()
    right_answers_count = len(
        problem.answer_set.filter(
            right=True,
            processed=False,
            group_specific_participant_data__participant_group=participant_group
        ))  # Getting right answers only from current group
    if variant == problem.right_variant.lower():
        print("Right answer from {} N{}".format(participant,
                                                right_answers_count + 1))
        is_right = True
    else:
        print("Wrong answer from {} - Right answers {}".format(
            participant, right_answers_count))
    if not problem.answer_set.filter(
            group_specific_participant_data=group_specific_participant_data,
            processed=False):
        answer = Answer(
            **{
                "problem":
                problem,
                "answer":
                variant,
                "right":
                is_right,
                "processed":
                False,
                "group_specific_participant_data":
                group_specific_participant_data,
                "date":
                timezone.now(),
            })
        answer.save()


available_entities = {
    "mention": -1,
    "hashtag": 1,
    "cashtag": 0,
    "bot_command": 0,
    "url": 2,
    "email": 1,
    "phone_number": 0,
    "bold": 0,
    "italic": 0,
    "code": 0,
    "pre": 0,
    "text_link": 3,
    "text_mention": -1,
}


def check_entities(bot: Bot, participant_group: ParticipantGroup,
                   participant: Participant, entities: list, message: dict):
    groupspecificparticipantdata = participant.groupspecificparticipantdata_set.filter(
        participant_group=participant_group)
    resp = {"status": True, "unknown": False}
    priority_level = -1
    if groupspecificparticipantdata:
        priority_level = max(
            (participantgroupbinding.role.priority_level
             for participantgroupbinding in groupspecificparticipantdata[0].
             participantgroupbinding_set.all()),
            default=0)
    for entity in entities:
        entity = entity["type"]
        if available_entities.get(entity) is None:
            resp["status"] = False
            resp["cause"] = "Unknown entity {}".format(entity)
            resp["unknown"] = True
            return resp
        if available_entities[entity] > priority_level:
            resp["status"] = False
            resp[
                "cause"] = "{} entity is not allowed for users with priority level lower than {}".format(
                    entity, available_entities[entity])
            return resp
    return resp


available_message_bindings = {
    "document": -1,
    "sticker": 0,
    "photo": 1,
    "audio": 2,
    "animation": 2,
    "voice": 2,
    "game": 3,
    "video": 3,
    "video_note": 3,
}


def check_message_bindings(bot: Bot, participant_group: ParticipantGroup,
                           participant: Participant, message: dict):
    groupspecificparticipantdata = participant.groupspecificparticipantdata_set.filter(
        participant_group=participant_group)
    resp = {"status": True, "unknown": False}
    priority_level = -1
    if groupspecificparticipantdata:
        priority_level = max(
            (participantgroupbinding.role.priority_level
             for participantgroupbinding in groupspecificparticipantdata[0].
             participantgroupbinding_set.all()),
            default=0)
    for message_binding in available_message_bindings:
        if message_binding in message and available_message_bindings[
                message_binding] > priority_level:
            resp["status"] = False
            if ("cause" not in resp):
                resp["cause"] = []
            resp["cause"].append(
                "\"{}\" message binding is not allowed for users with priority level lower than {}"
                .format(message_binding,
                        available_message_bindings[message_binding]))
    return resp


def update_bot(bot: Bot, *, timeout=10):
    """ Will get bot updates """
    url = bot.base_url + "getUpdates"
    payload = {'offset': bot.offset or "", 'timeout': timeout}
    resp = get_response(url, payload=payload)
    bot.last_updated = timezone.now()
    bot.save()
    for update in resp:
        message = update.get("message")
        if message and not message["from"]["is_bot"]:
            print("{} [{}] -> {}".format(
                message["from"].get("first_name")
                or message["from"].get("username")
                or message["from"].get("last_name"),
                bot,
                message.get("text")
                or (message.get('new_chat_member') and "New Chat Member")
                or (', '.join(key for key in available_message_bindings.keys()
                              if message.get(key))) or "|UNKNOWN|",
            ))
            logging.info("{}| {} [{}] -> {}".format(
                timezone.now(),
                message["from"].get("first_name")
                or message["from"].get("username")
                or message["from"].get("last_name"),
                bot,
                message.get("text") or message,
            ))
            try:
                participant_group = ParticipantGroup.objects.get(
                    telegram_id=message["chat"]["id"])
            except ParticipantGroup.DoesNotExist:
                bot.send_message(
                    message["chat"]["id"],
                    "Hi, if you want to use this bot in your groups too, then contact with @KoStard",
                )
                bot.offset = update["update_id"] + 1
                bot.save()
                continue

            if message.get("new_chat_members"):
                for new_chat_member_data in message["new_chat_members"]:
                    if new_chat_member_data[
                            "is_bot"] or Participant.objects.filter(
                                pk=new_chat_member_data["id"]):
                        continue
                    participant = Participant(
                        **{
                            "id": new_chat_member_data["id"],
                            "username": new_chat_member_data.get("username"),
                            "first_name": new_chat_member_data.get(
                                "first_name"),
                            "last_name": new_chat_member_data.get("last_name"),
                            "sum_score": 0,
                        })
                    participant.save()
                    GroupSpecificParticipantData(
                        **{
                            "participant":
                            participant,
                            "group":
                            participant_group,
                            "score":
                            0,
                            "joined":
                            datetime.fromtimestamp(
                                message["date"],
                                tz=timezone.get_current_timezone()),
                        }).save()
            try:
                participant = Participant.objects.get(pk=message["from"]["id"])
            except Participant.DoesNotExist:
                participant = Participant(
                    **{
                        "id": message["from"]["id"],
                        "username": message["from"].get("username"),
                        "first_name": message["from"].get("first_name"),
                        "last_name": message["from"].get("last_name"),
                        "sum_score": 0,
                    })
                participant.save()
                GroupSpecificParticipantData(
                    **{
                        "participant": participant,
                        "group": participant_group,
                        "score": 0
                    }).save()
            else:
                # Updating the participant information when getting an update from him/her
                participant.username = message["from"].get("username")
                participant.first_name = message["from"].get("first_name")
                participant.last_name = message["from"].get("last_name")
                participant.save()
            text = message.get("text")
            entities = message.get("entities")
            if entities:
                entities_check_resp = check_entities(
                    bot, participant_group, participant, entities, message)
                if not entities_check_resp["status"]:
                    logging.info(entities_check_resp["cause"])
                    if not entities_check_resp["unknown"]:
                        if not participant.groupspecificparticipantdata_set.filter(
                                participant_group=participant_group):
                            GroupSpecificParticipantData(
                                **{
                                    "participant": participant,
                                    "group": participant_group,
                                    "score": 0,
                                }).save()
                        bot.send_message(
                            participant_group,
                            "Dear {}, your message will be removed, because {}.\nYou have [{}] roles.\
                            \nFor more information contact with @KoStard".
                            format(
                                participant.name,
                                entities_check_resp["cause"],
                                ", ".join(
                                    "{} - {}".format(
                                        participantgroupbinding.role.name,
                                        participantgroupbinding.role.
                                        priority_level,
                                    )
                                    for participantgroupbinding in participant.
                                    groupspecificparticipantdata_set.get(
                                        participant_group=participant_group).
                                    participantgroupbinding_set.all()),
                            ),
                            reply_to_message_id=message["message_id"],
                        )
                        bot.delete_message(participant_group,
                                           message["message_id"])
                        bot.offset = update["update_id"] + 1
                        bot.save()
                        continue
            message_bindings_check_resp = check_message_bindings(
                bot, participant_group, participant, message)
            if not message_bindings_check_resp["status"]:
                logging.info(message_bindings_check_resp["cause"])
                if not message_bindings_check_resp["unknown"]:
                    if not participant.groupspecificparticipantdata_set.filter(
                            participant_group=participant_group):
                        GroupSpecificParticipantData(
                            **{
                                "participant": participant,
                                "group": participant_group,
                                "score": 0,
                            }).save()
                    bot.send_message(
                        participant_group,
                        "Dear {}, your message will be removed, because {}.\nYou have [{}] roles.\
                        \nFor more information contact with @KoStard".format(
                            participant.name,
                            ', '.join(message_bindings_check_resp["cause"]),
                            ", ".join("{} - {}".format(
                                participantgroupbinding.role.name,
                                participantgroupbinding.role.priority_level,
                            ) for participantgroupbinding in participant.
                                      groupspecificparticipantdata_set.get(
                                          participant_group=participant_group).
                                      participantgroupbinding_set.all()),
                        ),
                        reply_to_message_id=message["message_id"],
                    )
                    bot.delete_message(participant_group,
                                       message["message_id"])
                    bot.offset = update["update_id"] + 1
                    bot.save()
                    continue
            if text:
                if len(text) == 1 and (
                        ord(text) in range(ord("a"),
                                           ord("e") + 1)
                        or ord(text) in range(ord("A"),
                                              ord("E") + 1)):
                    if participant_group.activeProblem and BotBinding.objects.filter(
                            bot=bot, participant_group=participant_group):
                        participant_answering(participant, participant_group,
                                              participant_group.activeProblem,
                                              text)
                elif text[0] == "/":
                    command = text[1:].split(" ")[0].split('@')[0]
                    if command in available_commands:
                        participant_group_bindings = participant.groupspecificparticipantdata_set.get(
                            participant_group=participant_group
                        ).participantgroupbinding_set.all()
                        if participant_group_bindings:
                            max_priority_role = sorted(
                                participant_group_bindings,
                                key=lambda binding: binding.role.priority_level,
                            )[-1].role
                            priority_level = max_priority_role.priority_level
                        else:
                            max_priority_role = Role.objects.get(value='guest')
                            priority_level = -1
                        if priority_level >= available_commands[command][1]:
                            if available_commands[command][2]:
                                if not BotBinding.objects.filter(
                                        bot=bot,
                                        participant_group=participant_group):
                                    bot.send_message(
                                        participant_group,
                                        "Hi, if you want to use this bot in "
                                        "a new participant_group too, then contact with @KoStard",
                                        reply_to_message_id=message[
                                            "message_id"],
                                    )
                                    return
                            available_commands[command][0](
                                bot, participant_group, text, message)
                        else:
                            bot.send_message(
                                participant_group,
                                'Sorry dear {}, your role "{}" is not granted to use this command.'
                                .format(participant, max_priority_role.name),
                                reply_to_message_id=message["message_id"],
                            )
                    elif command:
                        bot.send_message(
                            participant_group,
                            'Invalid command "{}"'.format(command),
                            reply_to_message_id=message["message_id"],
                        )
            participant.save()
        bot.offset = update["update_id"] + 1
        bot.save()


def send_problem(bot: Bot, participant_group: ParticipantGroup, text, message):
    index = int(text.split()[1]) if len(
        text.split()
    ) > 1 else participant_group.activeSubjectGroupBinding.last_problem.next.index
    try:
        problem = participant_group.activeSubjectGroupBinding.subject.problem_set.get(
            index=index)
    except Problem.DoesNotExist:
        bot.send_message(
            participant_group,
            'Invalid problem number "{}".',
            reply_to_message_id=message["message_id"],
        )
    else:
        form_resp = bot.send_message(participant_group, str(problem))
        logging.debug("Sending problem {}".format(problem.index))
        if problem.img and form_resp:
            try:
                bot.send_image(
                    participant_group,
                    open("media/" + problem.img.name, "rb"),
                    reply_to_message_id=form_resp[0].get("message_id"),
                    caption="Image of problem N{}.".format(problem.index),
                )
                logging.debug("Sending image for problem {}".format(
                    problem.index))
            except Exception as e:
                print("Can't send image {}".format(problem.img))
        participant_group.activeProblem = problem
        participant_group.save()
        participant_group.activeSubjectGroupBinding.last_problem = problem
        participant_group.activeSubjectGroupBinding.save()


def answer_problem(bot, participant_group, text, message):
    if not participant_group.activeProblem and len(text.split()) <= 1:
        bot.send_message(
            participant_group,
            "There is no active problem for this participant_group.",
            reply_to_message_id=message["message_id"],
        )
        return
    problem = participant_group.activeProblem
    if len(text.split()) > 1:
        index = int(text.split()[1])
        if problem and index > problem.index:
            bot.send_message(
                participant_group,
                "You can't send new problem's answer without opening it.",
                reply_to_message_id=message["message_id"],
            )
            return
        elif not problem or index < problem.index:
            try:
                problem = participant_group.activeSubjectGroupBinding.subject.problem_set.get(
                    index=index)
            except Problem.DoesNotExist:
                bot.send_message(participant_group,
                                 "Invalid problem number {}.")
            else:
                bot.send_message(participant_group, problem.get_answer())
            return
    bot.send_message(participant_group, problem.get_answer())
    bot.send_message(participant_group, problem.close(participant_group))
    t_pages = participant_group.telegraphpage_set.all()
    if t_pages:  # Create the page manually with DynamicTelegraphPageCreator
        t_page = t_pages[
            len(t_pages) -
            1]  # Using last added page -> negative indexing is not supported
        t_account = t_page.account
        page_controller = DynamicTelegraphPageCreator(t_account.access_token)
        page_controller.load_and_set_page(t_page.path, return_content=False)
        page_controller.update_page(
            content=createGroupLeaderBoardForTelegraph(participant_group))
    participant_group.activeProblem = None
    participant_group.save()


def start_in_participant_group(bot, participant_group, text, message):
    binding = BotBinding(bot=bot, participant_group=participant_group)
    binding.save()
    bot.send_message(
        participant_group,
        "This participant_group is now bound with me, to break the connection, use /stop command.",
        reply_to_message_id=message["message_id"],
    )


def remove_from_participant_group(bot, participant_group, text, message):
    bot.botbinding_set.objects.get(bot=bot).delete()
    bot.send_message(
        participant_group,
        "The connection was successfully stopped.",
        reply_to_message_id=message["message_id"],
    )


def add_subject(bot, participant_group, text, message):
    pass


def select_subject(bot, participant_group, text, message):
    pass


def finish_subject(bot, participant_group, text, message):
    pass


def get_score(bot, participant_group, text, message):
    participant = Participant.objects.filter(pk=message["from"]["id"])
    if participant:
        participant = participant[0]
        specific = GroupSpecificParticipantData.objects.filter(
            participant=participant, participant_group=participant_group)
        if specific:
            specific = specific[0]
            bot.send_message(
                participant_group,
                "{}'s score is {}".format(str(participant), specific.score),
                reply_to_message_id=message["message_id"],
            )


def report(bot, participant_group, text, message):
    pass


#- (function, min_priority_level, needs_binding)
available_commands = {
    "send": (send_problem, 6, True),
    "answer": (answer_problem, 6, True),
    "start": (start_in_participant_group, 8, False),
    "stop": (remove_from_participant_group, 8, True),
    "add_subject": (add_subject, 9, True),
    "select_subject": (select_subject, 9, True),
    "finish_subject": (finish_subject, 9, True),
    "score": (get_score, 0, True),
    "report": (report, 2, True),
}


def createGroupLeaderBoard(participant_group: ParticipantGroup):
    gss = [{
        "participant":
        gs.participant,
        "score":
        gs.score,
        "percentage":
        gs.percentage,
        "standard_role":
        safe_getter(gs.highest_standard_role_binding, "role"),
        "non_standard_role":
        safe_getter(gs.highest_non_standard_role_binding, "role"),
    } for gs in sorted(
        (gs for gs in participant_group.groupspecificparticipantdata_set.all()
         if gs.score),
        key=lambda gs: [gs.score, gs.percentage],
    )[::-1]]
    return gss


def get_promoted_participants_list_for_leaderboard(
        participant_group: ParticipantGroup):
    admin_gss = [{
        "participant":
        gs.participant,
        "non_standard_role":
        gs.highest_non_standard_role_binding.role,
    } for gs in sorted(
        (gs for gs in participant_group.groupspecificparticipantdata_set.all()
         if gs.highest_non_standard_role_binding),
        key=
        lambda gs: [gs.highest_non_standard_role_binding.role.priority_level],
    )[::-1]]
    return admin_gss


def createGroupLeaderBoardForTelegraph(participant_group: ParticipantGroup,
                                       *,
                                       max_limit=0):
    raw_leaderboard = createGroupLeaderBoard(participant_group)
    raw_promoted_list = get_promoted_participants_list_for_leaderboard(
        participant_group)
    res = []

    res.append(
        DynamicTelegraphPageCreator.create_blockquote([
            "Here you see dynamically updating Leaderboard of ",
            DynamicTelegraphPageCreator.create_link(
                "Pathology Group [MedStard]",
                'https://t.me/Pathology_Group'), '.\n', "This is a part of ",
            DynamicTelegraphPageCreator.create_link("MedStard",
                                                    "https://t.me/MedStard"),
            ", where you can find much more stuff related to medicine, so welcome to our community."
        ]))

    last_role = None
    roles_number = 0
    current_list = None
    for gs in (raw_leaderboard[:max_limit] if max_limit else raw_leaderboard):
        if gs['standard_role'] != last_role:
            if last_role:
                res.append(DynamicTelegraphPageCreator.hr)
            roles_number += 1
            res.append(
                DynamicTelegraphPageCreator.create_title(
                    4, '{}. {} {}'.format(
                        roles_number, gs['standard_role'].name,
                        '⭐' * gs['standard_role'].priority_level)))
            l = DynamicTelegraphPageCreator.create_ordered_list()
            res.append(l)
            current_list = l['children']
            last_role = gs['standard_role']
        if roles_number == 1:
            current_list.append(
                DynamicTelegraphPageCreator.create_list_item(
                    DynamicTelegraphPageCreator.create_bold([
                        DynamicTelegraphPageCreator.create_code([
                            DynamicTelegraphPageCreator.create_bold(
                                '{}'.format(gs['score'])), 'xp{}'.format(
                                    (' [{}%]'.format(gs['percentage'])
                                     if gs['percentage'] is not None else ''))
                        ]), ' - {}'.format(gs['participant'].full_name)
                    ])))
        else:
            current_list.append(
                DynamicTelegraphPageCreator.create_list_item([
                    DynamicTelegraphPageCreator.create_code([
                        DynamicTelegraphPageCreator.create_bold('{}'.format(
                            gs['score'])), 'xp{}'.format(
                                (' [{}%]'.format(gs['percentage'])
                                 if gs['percentage'] is not None else ''))
                    ]), ' - {}'.format(gs['participant'].full_name)
                ]))
    res.append(DynamicTelegraphPageCreator.hr)
    res.append(
        DynamicTelegraphPageCreator.create_title(3, '{}'.format("Team")))
    l = DynamicTelegraphPageCreator.create_ordered_list()
    res.append(l)
    current_list = l['children']
    for gs in raw_promoted_list:
        current_list.append(
            DynamicTelegraphPageCreator.create_list_item(
                DynamicTelegraphPageCreator.create_bold([
                    gs['non_standard_role'].name + ' - ',
                    DynamicTelegraphPageCreator.create_link(
                        gs['participant'].full_name,
                        'https://telegram.me/{}'.format(
                            gs['participant'].username)) if
                    gs['participant'].username else gs['participant'].full_name
                ])))
    return res


def create_and_save_telegraph_page(t_account: TelegraphAccount,
                                   title: str,
                                   content: list,
                                   participant_group: ParticipantGroup = None):
    d = DynamicTelegraphPageCreator(t_account.access_token)
    p = d.create_page(title, content, return_content=True)
    d.load_and_set_page(p['path'])
    TelegraphPage(
        path=p['path'],
        url=p['url'],
        account=t_account,
        participant_group=participant_group).save()
    return d