from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import LoginForm, ParticipantProfileForm, QuizForm, RegistrationForm
from .models import Option, Participant, Question, Quiz, Result


def admin_required(view_func):

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            messages.error(request, 'You are not authorized to access this page.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def home(request):
    return render(request, 'quiz/home.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        User.objects.create_user(
            username=form.cleaned_data['username'],
            email=form.cleaned_data['email'],
            password=form.cleaned_data['password'],
        )
        messages.success(request, 'Registration successful. Please login.')
        return redirect('login')

    return render(request, 'quiz/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username_or_email = form.cleaned_data['username_or_email']
        password = form.cleaned_data['password']

        user = None
        if '@' in username_or_email:
            try:
                matched_user = User.objects.get(email=username_or_email)
                user = authenticate(request, username=matched_user.username, password=password)
            except User.DoesNotExist:
                user = None
        else:
            user = authenticate(request, username=username_or_email, password=password)

        if user is not None:
            login(request, user)
            if user.is_superuser:
                return redirect('admin_dashboard')
            return redirect('dashboard')

        messages.error(request, 'Invalid credentials.')

    return render(request, 'quiz/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    if request.user.is_superuser:
        return redirect('admin_dashboard')

    participant = Participant.objects.filter(user=request.user).first()
    profile_form = ParticipantProfileForm(request.POST or None, instance=participant)

    if request.method == 'POST':
        if profile_form.is_valid():
            participant_obj = profile_form.save(commit=False)
            participant_obj.user = request.user
            participant_obj.save()
            messages.success(request, 'Profile saved successfully.')
            return redirect('dashboard')
        messages.error(request, 'Please fix the profile form errors.')

    quizzes = Quiz.objects.all().order_by('-created_at')
    attempted_quiz_ids = []

    if participant:
        attempted_quiz_ids = list(
            Result.objects.filter(participant=participant).values_list('quiz_id', flat=True)
        )

    context = {
        'profile_form': profile_form,
        'participant': participant,
        'quizzes': quizzes,
        'attempted_quiz_ids': attempted_quiz_ids,
    }
    return render(request, 'quiz/dashboard.html', context)


@login_required
@admin_required
def admin_dashboard(request):
    quizzes = Quiz.objects.all().order_by('-created_at')
    return render(request, 'quiz/dashboard.html', {'quizzes': quizzes, 'admin_mode': True})


@login_required
def quiz_list(request):
    quizzes = Quiz.objects.all().order_by('-created_at')
    participant = Participant.objects.filter(user=request.user).first()
    attempted_quiz_ids = []

    if participant:
        attempted_quiz_ids = list(
            Result.objects.filter(participant=participant).values_list('quiz_id', flat=True)
        )

    return render(
        request,
        'quiz/quiz_list.html',
        {
            'quizzes': quizzes,
            'attempted_quiz_ids': attempted_quiz_ids,
        },
    )


@login_required
def create_quiz(request):
    form = QuizForm(request.POST or None)

    if request.method == 'POST':
        if not form.is_valid():
            messages.error(request, 'Please fix quiz title/description errors.')
            return render(
                request,
                'quiz/create_quiz.html',
                {'form': form, 'edit_mode': False, 'prefill_questions': []},
            )

        question_texts = request.POST.getlist('question_text[]')
        option_1_list = request.POST.getlist('option_1[]')
        option_2_list = request.POST.getlist('option_2[]')
        option_3_list = request.POST.getlist('option_3[]')
        option_4_list = request.POST.getlist('option_4[]')
        correct_options = request.POST.getlist('correct_option[]')

        total_questions = len(question_texts)

        if total_questions == 0:
            messages.error(request, 'Add at least one question.')
            return render(
                request,
                'quiz/create_quiz.html',
                {'form': form, 'edit_mode': False, 'prefill_questions': []},
            )

        if not (
            len(option_1_list) == len(option_2_list) == len(option_3_list) == len(option_4_list)
            == len(correct_options)
            == total_questions
        ):
            messages.error(request, 'Question and option data is incomplete.')
            return render(
                request,
                'quiz/create_quiz.html',
                {'form': form, 'edit_mode': False, 'prefill_questions': []},
            )

        for index in range(total_questions):
            if not question_texts[index].strip():
                messages.error(request, f'Question {index + 1} text is required.')
                return render(
                    request,
                    'quiz/create_quiz.html',
                    {'form': form, 'edit_mode': False, 'prefill_questions': []},
                )

            options = [
                option_1_list[index].strip(),
                option_2_list[index].strip(),
                option_3_list[index].strip(),
                option_4_list[index].strip(),
            ]
            if any(not option_text for option_text in options):
                messages.error(request, f'All 4 options are required for Question {index + 1}.')
                return render(
                    request,
                    'quiz/create_quiz.html',
                    {'form': form, 'edit_mode': False, 'prefill_questions': []},
                )

            if correct_options[index] not in ['0', '1', '2', '3']:
                messages.error(request, f'Select one correct option for Question {index + 1}.')
                return render(
                    request,
                    'quiz/create_quiz.html',
                    {'form': form, 'edit_mode': False, 'prefill_questions': []},
                )

        with transaction.atomic():
            quiz = form.save()

            for index in range(total_questions):
                question = Question.objects.create(quiz=quiz, text=question_texts[index].strip())
                options = [
                    option_1_list[index].strip(),
                    option_2_list[index].strip(),
                    option_3_list[index].strip(),
                    option_4_list[index].strip(),
                ]
                correct_index = int(correct_options[index])

                for option_index, option_text in enumerate(options):
                    Option.objects.create(
                        question=question,
                        text=option_text,
                        is_correct=(option_index == correct_index),
                    )

        messages.success(request, 'Quiz created successfully.')
        return redirect('admin_dashboard')

    return render(
        request,
        'quiz/create_quiz.html',
        {'form': form, 'edit_mode': False, 'prefill_questions': []},
    )


@login_required
@admin_required
def edit_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    form = QuizForm(request.POST or None, instance=quiz)

    if request.method == 'POST':
        if not form.is_valid():
            messages.error(request, 'Please fix quiz title/description errors.')
            return render(
                request,
                'quiz/create_quiz.html',
                {
                    'form': form,
                    'edit_mode': True,
                    'quiz': quiz,
                    'prefill_questions': _build_prefill_data(quiz),
                },
            )

        question_texts = request.POST.getlist('question_text[]')
        option_1_list = request.POST.getlist('option_1[]')
        option_2_list = request.POST.getlist('option_2[]')
        option_3_list = request.POST.getlist('option_3[]')
        option_4_list = request.POST.getlist('option_4[]')
        correct_options = request.POST.getlist('correct_option[]')
        total_questions = len(question_texts)

        if total_questions == 0:
            messages.error(request, 'Quiz must have at least one question.')
            return render(
                request,
                'quiz/create_quiz.html',
                {
                    'form': form,
                    'edit_mode': True,
                    'quiz': quiz,
                    'prefill_questions': _build_prefill_data(quiz),
                },
            )

        if not (
            len(option_1_list) == len(option_2_list) == len(option_3_list) == len(option_4_list)
            == len(correct_options)
            == total_questions
        ):
            messages.error(request, 'Question and option data is incomplete.')
            return render(
                request,
                'quiz/create_quiz.html',
                {
                    'form': form,
                    'edit_mode': True,
                    'quiz': quiz,
                    'prefill_questions': _build_prefill_data(quiz),
                },
            )

        for index in range(total_questions):
            if not question_texts[index].strip():
                messages.error(request, f'Question {index + 1} text is required.')
                return render(
                    request,
                    'quiz/create_quiz.html',
                    {
                        'form': form,
                        'edit_mode': True,
                        'quiz': quiz,
                        'prefill_questions': _build_prefill_data(quiz),
                    },
                )

            options = [
                option_1_list[index].strip(),
                option_2_list[index].strip(),
                option_3_list[index].strip(),
                option_4_list[index].strip(),
            ]
            if any(not option_text for option_text in options):
                messages.error(request, f'All 4 options are required for Question {index + 1}.')
                return render(
                    request,
                    'quiz/create_quiz.html',
                    {
                        'form': form,
                        'edit_mode': True,
                        'quiz': quiz,
                        'prefill_questions': _build_prefill_data(quiz),
                    },
                )

            if correct_options[index] not in ['0', '1', '2', '3']:
                messages.error(request, f'Select one correct option for Question {index + 1}.')
                return render(
                    request,
                    'quiz/create_quiz.html',
                    {
                        'form': form,
                        'edit_mode': True,
                        'quiz': quiz,
                        'prefill_questions': _build_prefill_data(quiz),
                    },
                )

        with transaction.atomic():
            form.save()
            quiz.questions.all().delete()

            for index in range(total_questions):
                question = Question.objects.create(quiz=quiz, text=question_texts[index].strip())
                options = [
                    option_1_list[index].strip(),
                    option_2_list[index].strip(),
                    option_3_list[index].strip(),
                    option_4_list[index].strip(),
                ]
                correct_index = int(correct_options[index])

                for option_index, option_text in enumerate(options):
                    Option.objects.create(
                        question=question,
                        text=option_text,
                        is_correct=(option_index == correct_index),
                    )

        messages.success(request, 'Quiz updated successfully.')
        return redirect('admin_dashboard')

    return render(
        request,
        'quiz/create_quiz.html',
        {
            'form': form,
            'edit_mode': True,
            'quiz': quiz,
            'prefill_questions': _build_prefill_data(quiz),
        },
    )


@login_required
@admin_required
def delete_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if request.method == 'POST':
        quiz.delete()
        messages.success(request, 'Quiz deleted successfully.')
        return redirect('admin_dashboard')

    return render(request, 'quiz/delete_quiz.html', {'quiz': quiz})


@login_required
def attempt_quiz(request, id):
    if request.user.is_superuser:
        messages.error(request, 'Admin cannot attempt quizzes.')
        return redirect('admin_dashboard')

    quiz = get_object_or_404(Quiz, id=id)
    participant = Participant.objects.filter(user=request.user).first()

    if not participant:
        messages.error(request, 'Please complete your profile before attempting a quiz.')
        return redirect('dashboard')

    if Result.objects.filter(participant=participant, quiz=quiz).exists():
        messages.error(request, 'You already attempted this quiz.')
        return redirect('quiz_list')

    questions = list(quiz.questions.order_by('?'))

    for question in questions:
        question.random_options = list(question.options.order_by('?'))

    if request.method == 'POST':
        score = 0
        total_questions = len(questions)

        for question in questions:
            selected_option_id = request.POST.get(f'question_{question.id}')
            if not selected_option_id:
                messages.error(request, 'Please answer all questions before submitting.')
                return render(
                    request,
                    'quiz/attempt_quiz.html',
                    {'quiz': quiz, 'questions': questions},
                )

            try:
                option = Option.objects.get(id=selected_option_id, question=question)
            except Option.DoesNotExist:
                messages.error(request, 'Invalid option selection detected.')
                return render(
                    request,
                    'quiz/attempt_quiz.html',
                    {'quiz': quiz, 'questions': questions},
                )

            if option.is_correct:
                score += 1

        result = Result.objects.create(participant=participant, quiz=quiz, score=score)
        messages.success(request, f'Quiz submitted. You scored {score} out of {total_questions}.')
        return redirect('result', id=result.id)

    return render(request, 'quiz/attempt_quiz.html', {'quiz': quiz, 'questions': questions})


@login_required
def result_view(request, id):
    result = get_object_or_404(Result, id=id)

    if request.user.is_superuser:
        pass
    else:
        participant = Participant.objects.filter(user=request.user).first()
        if not participant or result.participant != participant:
            messages.error(request, 'You are not allowed to view this result.')
            return redirect('dashboard')

    ranking = list(Result.objects.filter(quiz=result.quiz).order_by('-score', 'submitted_at'))
    position = ranking.index(result) + 1
    total_participants = len(ranking)

    return render(
        request,
        'quiz/result.html',
        {
            'result': result,
            'position': position,
            'total_participants': total_participants,
        },
    )


def _build_prefill_data(quiz):
    prefill_questions = []
    for question in quiz.questions.all().order_by('id'):
        options = list(question.options.all().order_by('id'))
        while len(options) < 4:
            options.append(None)

        correct_index = 0
        for index, option in enumerate(options[:4]):
            if option and option.is_correct:
                correct_index = index
                break

        prefill_questions.append(
            {
                'text': question.text,
                'options': [option.text if option else '' for option in options[:4]],
                'correct_index': correct_index,
            }
        )

    return prefill_questions
