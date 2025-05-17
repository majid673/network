from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .models import User, Post, Follow, Like  
import json


def index(request):
    if request.method == "POST":
        content = request.POST.get("content")
        if request.user.is_authenticated and content:
            Post.objects.create(user=request.user, content=content)
            return redirect("index")

    posts_list = Post.objects.all().order_by("-timestamp")
    paginator = Paginator(posts_list, 10)
    page_number = request.GET.get("page")
    posts = paginator.get_page(page_number)

    liked_posts = []
    if request.user.is_authenticated:
        liked_posts = Post.objects.filter(likes__user=request.user).values_list('id', flat=True)

    return render(request, "network/index.html", {
        "posts": posts,
        "liked_posts": liked_posts  
    })

def profile(request, username):
    try:
        user_profile = User.objects.get(username=username)
    except User.DoesNotExist:
        return render(request, "network/error.html", {
            "message": "User not found."
        })

    is_following = False
    if request.user.is_authenticated and request.user != user_profile:
        is_following = Follow.objects.filter(follower=request.user, following=user_profile).exists()

    followers_count = Follow.objects.filter(following=user_profile).count()
    following_count = Follow.objects.filter(follower=user_profile).count()

    posts = Post.objects.filter(user=user_profile).order_by("-timestamp")

    return render(request, "network/profile.html", {
        "profile_user": user_profile,
        "posts": posts,
        "followers_count": followers_count,
        "following_count": following_count,
        "is_following": is_following
    })


# ---------- Follow / Unfollow ----------
@csrf_exempt
@login_required
def toggle_follow(request, username):
    try:
        target_user = User.objects.get(username=username)
    except User.DoesNotExist:
        return HttpResponseRedirect(reverse("index"))

    if request.user == target_user:
        return HttpResponseRedirect(reverse("profile", args=[username]))

    follow_relation, created = Follow.objects.get_or_create(follower=request.user, following=target_user)
    if not created:
        follow_relation.delete()

    return HttpResponseRedirect(reverse("profile", args=[username]))


# ---------- Following ----------
@login_required
def following_posts(request):
    followed_users = Follow.objects.filter(follower=request.user).values_list('following', flat=True)
    posts_list = Post.objects.filter(user__in=followed_users).order_by('-timestamp')

    paginator = Paginator(posts_list, 10)
    page_number = request.GET.get("page")
    posts = paginator.get_page(page_number)

    return render(request, "network/following.html", {
        "posts": posts
    })


# ----------Edit post ----------
@csrf_exempt
@login_required
def edit_post(request, post_id):
    if request.method == "PUT":
        try:
            data = json.loads(request.body)
            new_content = data.get("content")
            post = Post.objects.get(pk=post_id)
            if post.user != request.user:
                return JsonResponse({"error": "Unauthorized"}, status=403)
            post.content = new_content
            post.save()
            return JsonResponse({"message": "Post updated successfully."})
        except Post.DoesNotExist:
            return JsonResponse({"error": "Post not found."}, status=404)
    return JsonResponse({"error": "Invalid request"}, status=400)


# ---------- Like / Unlike ----------
@csrf_exempt
@login_required
def toggle_like(request, post_id):
    try:
        post = Post.objects.get(pk=post_id)
    except Post.DoesNotExist:
        return JsonResponse({"error": "Post not found."}, status=404)

    if request.method == "PUT":
        like, created = Like.objects.get_or_create(user=request.user, post=post)
        if not created:
            like.delete()
            liked = False
        else:
            liked = True

        return JsonResponse({
            "liked": liked,
            "likes_count": post.likes.count()
        })

    return JsonResponse({"error": "Invalid request"}, status=400)


# ---------- Login, Logout, Register ----------
def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "network/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "network/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]

        if password != confirmation:
            return render(request, "network/register.html", {
                "message": "Passwords must match."
            })

        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "network/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "network/register.html")

